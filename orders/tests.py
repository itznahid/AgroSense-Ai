"""
orders/tests.py
===============
Covers: models, services, permissions, views (workflow & security).
Run with:  python manage.py test orders
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import MerchantProfile, UserAccount
from marketplace.models import Cart, CartItem, Category, Product
from orders.models import Notification, Order, OrderItem, ShippingAddress
from orders.permissions import (
    assert_customer_owns_order,
    assert_merchant_owns_order,
    customer_can_cancel,
)
from orders.services import (
    create_orders_from_cart,
    customer_cancel_order,
    customer_confirm_delivery,
    merchant_accept_order,
    merchant_mark_delivered,
    merchant_mark_processing,
    merchant_mark_shipped,
    merchant_reject_order,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_user(username, role='user'):
    user = User.objects.create_user(username=username, password='testpass123')
    account = UserAccount.objects.create(user=user, role=role, phone='01700000000')
    if role == 'merchant':
        MerchantProfile.objects.create(
            account=account, shop_name=f"{username}'s Shop"
        )
    return user, account


def _make_product(merchant_account, name='Test Product', price='100.00', stock=50):
    cat, _ = Category.objects.get_or_create(
        slug='test-cat',
        defaults={'name': 'Test Category', 'icon': '🌱', 'order': 0},
    )
    return Product.objects.create(
        name=name, category=cat, description='desc',
        price=Decimal(price), unit='kg', stock=stock,
        merchant=merchant_account, is_active=True,
    )


def _shipping():
    return {
        'full_name':    'Test Buyer',
        'phone':        '01712345678',
        'district':     'Dhaka',
        'area':         'Mirpur',
        'full_address': '123 Test Road',
        'notes':        '',
    }


# ══════════════════════════════════════════════════════════════════════════════
# MODEL TESTS
# ══════════════════════════════════════════════════════════════════════════════

class OrderModelTests(TestCase):

    def setUp(self):
        self.customer, self.cust_acct  = _make_user('customer')
        self.merchant, self.merch_acct = _make_user('merchant', 'merchant')

    def _make_order(self, status=Order.STATUS_PENDING):
        return Order.objects.create(
            order_number  = 'AGR-TEST-001',
            customer      = self.customer,
            merchant      = self.merch_acct,
            status        = status,
            subtotal      = Decimal('200.00'),
            shipping_cost = Decimal('60.00'),
            tax           = Decimal('0.00'),
            total_amount  = Decimal('260.00'),
        )

    def test_str(self):
        order = self._make_order()
        self.assertIn('AGR-TEST-001', str(order))

    def test_is_cancellable_by_customer_pending(self):
        order = self._make_order(Order.STATUS_PENDING)
        self.assertTrue(order.is_cancellable_by_customer)

    def test_is_cancellable_by_customer_confirmed(self):
        order = self._make_order(Order.STATUS_CONFIRMED)
        self.assertFalse(order.is_cancellable_by_customer)

    def test_is_rejectable_by_merchant_pending(self):
        order = self._make_order(Order.STATUS_PENDING)
        self.assertTrue(order.is_rejectable_by_merchant)

    def test_is_confirmable_by_customer_delivered(self):
        order = self._make_order(Order.STATUS_DELIVERED)
        self.assertTrue(order.is_confirmable_by_customer)

    def test_merchant_next_statuses_pending(self):
        order = self._make_order(Order.STATUS_PENDING)
        self.assertIn(Order.STATUS_CONFIRMED, order.merchant_next_statuses())
        self.assertIn(Order.STATUS_REJECTED,  order.merchant_next_statuses())

    def test_merchant_next_statuses_completed(self):
        order = self._make_order(Order.STATUS_COMPLETED)
        self.assertEqual(order.merchant_next_statuses(), [])

    def test_badge_classes_returns_string(self):
        order = self._make_order()
        self.assertIsInstance(order.badge_classes, str)


# ══════════════════════════════════════════════════════════════════════════════
# SERVICE TESTS
# ══════════════════════════════════════════════════════════════════════════════

class CreateOrdersFromCartTests(TestCase):

    def setUp(self):
        self.customer, self.cust_acct  = _make_user('customer')
        self.merchant, self.merch_acct = _make_user('merchant', 'merchant')
        self.product = _make_product(self.merch_acct, stock=10)
        self.cart, _  = Cart.objects.get_or_create(user=self.customer)

    def _add_to_cart(self, qty=2):
        CartItem.objects.create(cart=self.cart, product=self.product, quantity=qty)

    def test_creates_order_and_clears_cart(self):
        self._add_to_cart(2)
        orders = create_orders_from_cart(self.customer, self.cart, _shipping())
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].status, Order.STATUS_PENDING)
        self.assertEqual(self.cart.items.count(), 0)

    def test_stock_decremented(self):
        self._add_to_cart(3)
        create_orders_from_cart(self.customer, self.cart, _shipping())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 7)

    def test_shipping_address_created(self):
        self._add_to_cart(1)
        orders = create_orders_from_cart(self.customer, self.cart, _shipping())
        self.assertTrue(ShippingAddress.objects.filter(order=orders[0]).exists())

    def test_notifications_created(self):
        self._add_to_cart(1)
        create_orders_from_cart(self.customer, self.cart, _shipping())
        self.assertTrue(Notification.objects.filter(user=self.customer).exists())
        self.assertTrue(Notification.objects.filter(user=self.merchant).exists())

    def test_empty_cart_raises(self):
        with self.assertRaises(ValueError):
            create_orders_from_cart(self.customer, self.cart, _shipping())

    def test_insufficient_stock_raises_and_no_order(self):
        self._add_to_cart(qty=999)
        with self.assertRaises(ValueError):
            create_orders_from_cart(self.customer, self.cart, _shipping())
        self.assertEqual(Order.objects.count(), 0)

    def test_multi_merchant_creates_multiple_orders(self):
        _, merch2 = _make_user('merchant2', 'merchant')
        prod2 = _make_product(merch2, name='Product2', stock=5)
        CartItem.objects.create(cart=self.cart, product=self.product, quantity=1)
        CartItem.objects.create(cart=self.cart, product=prod2, quantity=1)
        orders = create_orders_from_cart(self.customer, self.cart, _shipping())
        self.assertEqual(len(orders), 2)


class OrderWorkflowTests(TestCase):

    def setUp(self):
        self.customer, self.cust_acct  = _make_user('customer')
        self.merchant, self.merch_acct = _make_user('merchant', 'merchant')
        self.product = _make_product(self.merch_acct, stock=10)
        cart, _ = Cart.objects.get_or_create(user=self.customer)
        CartItem.objects.create(cart=cart, product=self.product, quantity=2)
        orders = create_orders_from_cart(self.customer, cart, _shipping())
        self.order = orders[0]

    def test_full_happy_path(self):
        merchant_accept_order(self.order, self.merchant)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_CONFIRMED)

        merchant_mark_processing(self.order, self.merchant)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_PROCESSING)

        merchant_mark_shipped(self.order, self.merchant)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_SHIPPED)

        merchant_mark_delivered(self.order, self.merchant)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_DELIVERED)

        customer_confirm_delivery(self.order, self.customer)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_COMPLETED)

    def test_merchant_reject_restores_stock(self):
        self.product.refresh_from_db()
        initial_stock = self.product.stock  # already decremented by setUp
        merchant_reject_order(self.order, self.merchant)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, initial_stock + 2)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_REJECTED)

    def test_customer_cancel_restores_stock(self):
        self.product.refresh_from_db()
        initial_stock = self.product.stock
        customer_cancel_order(self.order, self.customer)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, initial_stock + 2)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_CANCELLED)

    def test_invalid_transition_raises(self):
        # Cannot skip CONFIRMED → SHIPPED directly
        merchant_accept_order(self.order, self.merchant)
        self.order.refresh_from_db()
        with self.assertRaises(ValueError):
            merchant_mark_shipped(self.order, self.merchant)

    def test_status_history_logged(self):
        merchant_accept_order(self.order, self.merchant)
        history = self.order.history.order_by('timestamp')
        # Initial PENDING + CONFIRMED
        statuses = [h.new_status for h in history]
        self.assertIn(Order.STATUS_PENDING,   statuses)
        self.assertIn(Order.STATUS_CONFIRMED, statuses)


# ══════════════════════════════════════════════════════════════════════════════
# PERMISSION TESTS
# ══════════════════════════════════════════════════════════════════════════════

class PermissionTests(TestCase):

    def setUp(self):
        self.customer,  self.cust_acct   = _make_user('customer')
        self.customer2, self.cust2_acct  = _make_user('customer2')
        self.merchant,  self.merch_acct  = _make_user('merchant', 'merchant')
        self.merchant2, self.merch2_acct = _make_user('merchant2', 'merchant')

        prod = _make_product(self.merch_acct, stock=5)
        cart, _ = Cart.objects.get_or_create(user=self.customer)
        CartItem.objects.create(cart=cart, product=prod, quantity=1)
        orders = create_orders_from_cart(self.customer, cart, _shipping())
        self.order = orders[0]

    def test_customer_owns_order(self):
        from django.core.exceptions import PermissionDenied
        with self.assertRaises(PermissionDenied):
            assert_customer_owns_order(self.order, self.customer2)

    def test_merchant_owns_order(self):
        from django.core.exceptions import PermissionDenied
        with self.assertRaises(PermissionDenied):
            assert_merchant_owns_order(self.order, self.merch2_acct)

    def test_customer_can_cancel_pending(self):
        self.assertTrue(customer_can_cancel(self.order, self.customer))

    def test_customer_cannot_cancel_other_order(self):
        self.assertFalse(customer_can_cancel(self.order, self.customer2))


# ══════════════════════════════════════════════════════════════════════════════
# VIEW TESTS (security + workflow)
# ══════════════════════════════════════════════════════════════════════════════

class CustomerViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.customer, _          = _make_user('viewcust')
        self.merchant, merch_acct = _make_user('viewmerch', 'merchant')
        prod = _make_product(merch_acct, stock=10)
        cart, _ = Cart.objects.get_or_create(user=self.customer)
        CartItem.objects.create(cart=cart, product=prod, quantity=1)
        orders = create_orders_from_cart(self.customer, cart, _shipping())
        self.order = orders[0]

    def test_my_orders_requires_login(self):
        resp = self.client.get(reverse('orders:my_orders'))
        self.assertRedirects(resp, reverse('accounts:login'),
                             fetch_redirect_response=False)

    def test_my_orders_shows_own_orders(self):
        self.client.login(username='viewcust', password='testpass123')
        resp = self.client.get(reverse('orders:my_orders'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn(self.order, resp.context['orders'])

    def test_order_detail_forbidden_for_other_user(self):
        other, _ = _make_user('other_user')
        self.client.login(username='other_user', password='testpass123')
        resp = self.client.get(
            reverse('orders:order_detail', kwargs={'order_id': self.order.pk})
        )
        self.assertEqual(resp.status_code, 403)

    def test_cancel_order_post_only(self):
        self.client.login(username='viewcust', password='testpass123')
        resp = self.client.get(
            reverse('orders:cancel_order', kwargs={'order_id': self.order.pk})
        )
        self.assertEqual(resp.status_code, 405)

    def test_cancel_order_success(self):
        self.client.login(username='viewcust', password='testpass123')
        resp = self.client.post(
            reverse('orders:cancel_order', kwargs={'order_id': self.order.pk})
        )
        self.assertRedirects(resp, reverse('orders:my_orders'),
                             fetch_redirect_response=False)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_CANCELLED)


class MerchantViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.customer, _           = _make_user('mcust')
        self.merchant, merch_acct  = _make_user('mmerch', 'merchant')
        self.merchant2, merch2_acct = _make_user('mmerch2', 'merchant')
        prod = _make_product(merch_acct, stock=10)
        cart, _ = Cart.objects.get_or_create(user=self.customer)
        CartItem.objects.create(cart=cart, product=prod, quantity=1)
        orders = create_orders_from_cart(self.customer, cart, _shipping())
        self.order = orders[0]

    def test_merchant_order_list_requires_login(self):
        resp = self.client.get(reverse('orders:merchant_order_list'))
        self.assertRedirects(resp, reverse('accounts:login'),
                             fetch_redirect_response=False)

    def test_customer_cannot_access_merchant_view(self):
        self.client.login(username='mcust', password='testpass123')
        resp = self.client.get(reverse('orders:merchant_order_list'))
        self.assertRedirects(resp, reverse('accounts:user_dashboard'),
                             fetch_redirect_response=False)

    def test_other_merchant_cannot_accept_order(self):
        self.client.login(username='mmerch2', password='testpass123')
        resp = self.client.post(
            reverse('orders:accept_order', kwargs={'order_id': self.order.pk})
        )
        self.assertEqual(resp.status_code, 403)

    def test_merchant_accept_order(self):
        self.client.login(username='mmerch', password='testpass123')
        self.client.post(
            reverse('orders:accept_order', kwargs={'order_id': self.order.pk})
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_CONFIRMED)


# ══════════════════════════════════════════════════════════════════════════════
# INVENTORY TESTS
# ══════════════════════════════════════════════════════════════════════════════

class InventoryTests(TestCase):

    def setUp(self):
        self.customer, _           = _make_user('invcust')
        self.merchant,  merch_acct = _make_user('invmerch', 'merchant')
        self.product = _make_product(merch_acct, stock=3)

    def test_checkout_reduces_stock(self):
        cart, _ = Cart.objects.get_or_create(user=self.customer)
        CartItem.objects.create(cart=cart, product=self.product, quantity=3)
        create_orders_from_cart(self.customer, cart, _shipping())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 0)

    def test_oversell_prevented(self):
        cart, _ = Cart.objects.get_or_create(user=self.customer)
        CartItem.objects.create(cart=cart, product=self.product, quantity=10)
        with self.assertRaises(ValueError):
            create_orders_from_cart(self.customer, cart, _shipping())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)  # unchanged

    def test_reject_restores_stock(self):
        cart, _ = Cart.objects.get_or_create(user=self.customer)
        CartItem.objects.create(cart=cart, product=self.product, quantity=2)
        orders = create_orders_from_cart(self.customer, cart, _shipping())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 1)

        merchant_reject_order(orders[0], self.merchant)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)
