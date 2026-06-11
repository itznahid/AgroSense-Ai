"""
orders/services.py
==================
All business logic lives here.  Views are kept thin — they validate
HTTP concerns (auth, CSRF, method) and then delegate to these functions.

Key design decisions
--------------------
* create_orders_from_cart() splits the cart by merchant so each merchant
  gets exactly one Order.  This keeps accept/reject/ship workflow clean.
* Every mutating function is wrapped in @transaction.atomic so stock
  updates and status writes are always consistent.
* Stock is restored via F() expressions (not read-modify-write) to avoid
  the race condition that can occur between two concurrent transactions.
"""

import random
import string
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from marketplace.models import Cart, Product
from .models import Order, OrderItem, ShippingAddress, OrderStatusHistory, Notification


# ── Helpers ───────────────────────────────────────────────────────────────────

def _generate_order_number() -> str:
    today = timezone.now().strftime('%Y%m%d')
    for _ in range(10):
        suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        num = f"AGR-{today}-{suffix}"
        if not Order.objects.filter(order_number=num).exists():
            return num
    raise RuntimeError("Could not generate a unique order number after 10 attempts.")


def _notify(user, message: str) -> None:
    Notification.objects.create(user=user, message=message)


def _log_transition(order: Order, old_status: str, new_status: str, actor) -> None:
    OrderStatusHistory.objects.create(
        order           = order,
        previous_status = old_status,
        new_status      = new_status,
        changed_by      = actor,
    )


def _restore_stock(order: Order) -> None:
    """Return item quantities to product stock (called on cancel / reject)."""
    for item in order.items.select_related('product').all():
        if item.product_id:
            Product.objects.filter(pk=item.product_id).update(
                stock=F('stock') + item.quantity
            )


# ── Notification dispatch ─────────────────────────────────────────────────────

_CUSTOMER_MESSAGES = {
    Order.STATUS_CONFIRMED:  "🎉 Order #{num} confirmed by the merchant!",
    Order.STATUS_PROCESSING: "📦 Order #{num} is being prepared.",
    Order.STATUS_SHIPPED:    "🚚 Order #{num} shipped! Watch out for your delivery.",
    Order.STATUS_DELIVERED:  "📬 Order #{num} delivered. Please confirm receipt in the app.",
    Order.STATUS_REJECTED:   "❌ Order #{num} was rejected by the merchant.",
}
_MERCHANT_MESSAGES = {
    Order.STATUS_COMPLETED: "✅ Order #{num} confirmed delivered by the customer.",
    Order.STATUS_CANCELLED: "🚫 Order #{num} was cancelled by the customer.",
}


def _dispatch_notifications(order: Order, new_status: str) -> None:
    num = order.order_number
    if new_status in _CUSTOMER_MESSAGES:
        _notify(order.customer, _CUSTOMER_MESSAGES[new_status].format(num=num))
    if new_status in _MERCHANT_MESSAGES:
        _notify(order.merchant.user, _MERCHANT_MESSAGES[new_status].format(num=num))


# ── Core transition helper ────────────────────────────────────────────────────

def _apply_transition(order: Order, new_status: str, actor,
                      allowed_map: dict) -> Order:
    allowed = allowed_map.get(order.status, [])
    if new_status not in allowed:
        raise ValueError(
            f"Cannot move order from '{order.get_status_display()}' "
            f"to '{new_status}'."
        )
    old_status   = order.status
    order.status = new_status
    order.save(update_fields=['status', 'updated_at'])
    _log_transition(order, old_status, new_status, actor)
    _dispatch_notifications(order, new_status)
    return order


# ══════════════════════════════════════════════════════════════════════════════
# ORDER CREATION
# ══════════════════════════════════════════════════════════════════════════════

@transaction.atomic
def create_orders_from_cart(customer, cart: Cart, shipping_data: dict) -> list:
    """
    Split the cart by merchant and create one Order per merchant group.

    shipping_data expected keys
    ---------------------------
    full_name, phone, district, area, full_address, notes (optional)

    Returns
    -------
    list[Order]  – one Order per merchant, in insertion order.

    Raises
    ------
    ValueError   – cart empty / all items unorderable / insufficient stock.
    """
    items = list(
        cart.items
        .select_related('product', 'product__merchant')
        .all()
    )
    if not items:
        raise ValueError("Your cart is empty.")

    # --- Group by merchant --------------------------------------------------
    # FIX: previously any item with merchant=None raised ValueError immediately,
    # aborting the *entire* checkout so zero orders were ever created.
    # Now we skip unassigned products and continue with the rest.
    # If ALL items are unassigned, we raise a single clear error.
    merchant_groups: dict = {}
    skipped_names:   list = []

    for ci in items:
        if ci.product.merchant_id is None:
            skipped_names.append(ci.product.name)
            continue
        merchant_groups.setdefault(ci.product.merchant, []).append(ci)

    if not merchant_groups:
        raise ValueError(
            "None of your cart items are currently available for ordering. "
            "These products are not yet assigned to a shop: "
            + ", ".join(skipped_names) + "."
        )

    # --- First pass: validate stock (fail before any writes) ----------------
    for _merchant, cart_items in merchant_groups.items():
        for ci in cart_items:
            locked = Product.objects.select_for_update().get(pk=ci.product_id)
            if locked.stock < ci.quantity:
                raise ValueError(
                    f"'{locked.name}' only has {locked.stock} unit(s) in stock. "
                    f"You requested {ci.quantity}."
                )

    # --- Second pass: create orders -----------------------------------------
    SHIPPING_COST = Decimal("60.00")
    TAX_RATE      = Decimal("0.00")

    created_orders: list[Order] = []
    ordered_product_ids: set    = set()

    for merchant, cart_items in merchant_groups.items():
        subtotal      = sum(ci.product.price * ci.quantity for ci in cart_items)
        shipping_cost = SHIPPING_COST
        tax           = (subtotal * TAX_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total_amount  = subtotal + shipping_cost + tax

        order = Order.objects.create(
            order_number  = _generate_order_number(),
            customer      = customer,
            merchant      = merchant,
            status        = Order.STATUS_PENDING,
            subtotal      = subtotal,
            shipping_cost = shipping_cost,
            tax           = tax,
            total_amount  = total_amount,
            notes         = shipping_data.get('notes', ''),
        )

        ShippingAddress.objects.create(
            order        = order,
            full_name    = shipping_data['full_name'],
            phone        = shipping_data['phone'],
            district     = shipping_data['district'],
            area         = shipping_data['area'],
            full_address = shipping_data['full_address'],
        )

        for ci in cart_items:
            locked = Product.objects.select_for_update().get(pk=ci.product_id)
            if locked.stock < ci.quantity:
                raise ValueError(
                    f"'{locked.name}' stock changed while placing order. "
                    "Please review your cart."
                )
            OrderItem.objects.create(
                order                  = order,
                product                = ci.product,
                product_name_snapshot  = ci.product.name,
                product_price_snapshot = ci.product.price,
                quantity               = ci.quantity,
                total_price            = ci.product.price * ci.quantity,
            )
            updated = Product.objects.filter(
                pk=locked.pk,
                stock__gte=ci.quantity,
            ).update(stock=F('stock') - ci.quantity)
            if updated != 1:
                raise ValueError(
                    f"'{locked.name}' stock changed while placing order. "
                    "Please review your cart."
                )
            ordered_product_ids.add(ci.product_id)

        _log_transition(order, '', Order.STATUS_PENDING, customer)

        shop_name = getattr(
            getattr(merchant, 'merchant_profile', None),
            'shop_name',
            merchant.user.username,
        )
        _notify(
            merchant.user,
            f"🛒 New order #{order.order_number} received from "
            f"{customer.get_full_name() or customer.username}.",
        )
        _notify(
            customer,
            f"✅ Order #{order.order_number} placed with {shop_name}! "
            "Awaiting merchant confirmation.",
        )

        created_orders.append(order)

    # FIX: only remove the cart items that were successfully ordered.
    # Previously cart.items.all().delete() wiped everything including items
    # that were skipped due to having no merchant — those items stay in the
    # cart so the user can see them and take action.
    cart.items.filter(product_id__in=ordered_product_ids).delete()

    return created_orders


# ══════════════════════════════════════════════════════════════════════════════
# MERCHANT ACTIONS
# ══════════════════════════════════════════════════════════════════════════════

@transaction.atomic
def merchant_accept_order(order: Order, actor) -> Order:
    return _apply_transition(order, Order.STATUS_CONFIRMED, actor,
                             Order.MERCHANT_TRANSITIONS)


@transaction.atomic
def merchant_reject_order(order: Order, actor) -> Order:
    _restore_stock(order)
    return _apply_transition(order, Order.STATUS_REJECTED, actor,
                             Order.MERCHANT_TRANSITIONS)


@transaction.atomic
def merchant_mark_processing(order: Order, actor) -> Order:
    return _apply_transition(order, Order.STATUS_PROCESSING, actor,
                             Order.MERCHANT_TRANSITIONS)


@transaction.atomic
def merchant_mark_shipped(order: Order, actor) -> Order:
    return _apply_transition(order, Order.STATUS_SHIPPED, actor,
                             Order.MERCHANT_TRANSITIONS)


@transaction.atomic
def merchant_mark_delivered(order: Order, actor) -> Order:
    return _apply_transition(order, Order.STATUS_DELIVERED, actor,
                             Order.MERCHANT_TRANSITIONS)


# ══════════════════════════════════════════════════════════════════════════════
# CUSTOMER ACTIONS
# ══════════════════════════════════════════════════════════════════════════════

@transaction.atomic
def customer_cancel_order(order: Order, actor) -> Order:
    _restore_stock(order)
    return _apply_transition(order, Order.STATUS_CANCELLED, actor,
                             Order.CUSTOMER_TRANSITIONS)


@transaction.atomic
def customer_confirm_delivery(order: Order, actor) -> Order:
    return _apply_transition(order, Order.STATUS_COMPLETED, actor,
                             Order.CUSTOMER_TRANSITIONS)
