"""
orders/views.py
===============
Thin views — HTTP plumbing only.
All business logic is delegated to orders.services.
All permission checks use orders.permissions helpers.
"""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from accounts.decorators import login_required, merchant_required, user_required
from marketplace.models import Cart

from .forms import CheckoutForm
from .models import Notification, Order
from .permissions import assert_customer_owns_order, assert_merchant_owns_order
from .services import (
    create_orders_from_cart,
    customer_cancel_order,
    customer_confirm_delivery,
    merchant_accept_order,
    merchant_mark_delivered,
    merchant_mark_processing,
    merchant_mark_shipped,
    merchant_reject_order,
)


# ── Cart helper ───────────────────────────────────────────────────────────────

def _get_or_create_cart(user) -> Cart:
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


# ══════════════════════════════════════════════════════════════════════════════
# CUSTOMER  –  Checkout
# ══════════════════════════════════════════════════════════════════════════════

@user_required
def checkout_view(request):
    cart  = _get_or_create_cart(request.user)
    items = cart.items.select_related('product', 'product__merchant',
                                      'product__merchant__merchant_profile').all()

    if not items.exists():
        messages.warning(request, 'Your cart is empty.')
        return redirect('cart')

    account = getattr(request.user, 'account', None)
    initial = {
        'full_name': request.user.get_full_name() or request.user.username,
        'phone':     getattr(account, 'phone', ''),
    }

    form = CheckoutForm(request.POST or None, initial=initial)

    if request.method == 'POST' and form.is_valid():
        try:
            orders = create_orders_from_cart(
                customer      = request.user,
                cart          = cart,
                shipping_data = form.cleaned_data,
            )
            if len(orders) == 1:
                messages.success(
                    request,
                    f"🎉 Order #{orders[0].order_number} placed successfully!",
                )
            else:
                nums = ', '.join(f"#{o.order_number}" for o in orders)
                messages.success(
                    request,
                    f"🎉 {len(orders)} orders placed: {nums}",
                )
            return redirect('orders:my_orders')
        except ValueError as exc:
            messages.error(request, str(exc))

    # Group for display (merchant breakdown in sidebar)
    merchant_groups: dict = {}
    for ci in items:
        merchant_groups.setdefault(ci.product.merchant, []).append(ci)

    return render(request, 'orders/customer/checkout.html', {
        'form':            form,
        'cart':            cart,
        'items':           items,
        'merchant_groups': merchant_groups,
    })


# ══════════════════════════════════════════════════════════════════════════════
# CUSTOMER  –  Order history & actions
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def my_orders(request):
    qs = (
        Order.objects
        .filter(customer=request.user)
        .select_related('merchant', 'merchant__merchant_profile', 'shipping_address')
        .prefetch_related('items')
        .order_by('-created_at')
    )

    status_filter = request.GET.get('status', '').strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    return render(request, 'orders/customer/my_orders.html', {
        'orders':         qs,
        'status_filter':  status_filter,
        'status_choices': Order.STATUS_CHOICES,
        'STATUS':         Order,
    })


@login_required
def order_detail(request, order_id):
    order = get_object_or_404(
        Order.objects
        .select_related('merchant', 'merchant__merchant_profile', 'shipping_address')
        .prefetch_related('items', 'history', 'history__changed_by'),
        pk=order_id,
    )
    assert_customer_owns_order(order, request.user)
    return render(request, 'orders/customer/order_detail.html', {
        'order':  order,
        'STATUS': Order,
    })


@require_POST
@login_required
def cancel_order(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    assert_customer_owns_order(order, request.user)

    if not order.is_cancellable_by_customer:
        messages.error(
            request,
            f"Order #{order.order_number} cannot be cancelled at this stage."
        )
        return redirect('orders:order_detail', order_id=order_id)

    try:
        customer_cancel_order(order, request.user)
        messages.success(request, f"Order #{order.order_number} has been cancelled.")
    except ValueError as exc:
        messages.error(request, str(exc))

    return redirect('orders:my_orders')


@require_POST
@login_required
def confirm_delivery(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    assert_customer_owns_order(order, request.user)

    if not order.is_confirmable_by_customer:
        messages.error(request, "Order cannot be confirmed at this stage.")
        return redirect('orders:order_detail', order_id=order_id)

    try:
        customer_confirm_delivery(order, request.user)
        messages.success(
            request,
            f"✅ Order #{order.order_number} marked as completed. Thank you!"
        )
    except ValueError as exc:
        messages.error(request, str(exc))

    return redirect('orders:order_detail', order_id=order_id)


# ══════════════════════════════════════════════════════════════════════════════
# MERCHANT  –  Order list views
# ══════════════════════════════════════════════════════════════════════════════

@merchant_required
def merchant_order_list(request):
    account       = request.user.account
    status_filter = request.GET.get('status', '').strip()

    qs = (
        Order.objects
        .filter(merchant=account)
        .select_related('customer', 'shipping_address')
        .prefetch_related('items')
        .order_by('-created_at')
    )
    if status_filter:
        qs = qs.filter(status=status_filter)

    # FIX: was `counts = {s[0]: ... for s in STATUS_CHOICES}` (a plain dict).
    # Django templates cannot do variable-key dict lookups — {{ counts.value }}
    # looks up the literal string "value", not the loop variable, so every card
    # showed the entire serialised dict instead of the per-status number.
    # Replaced with a list of (value, label, count) tuples so the template can
    # unpack with {% for value, label, count in status_counts %}.
    status_counts = [
        (s[0], s[1], Order.objects.filter(merchant=account, status=s[0]).count())
        for s in Order.STATUS_CHOICES
    ]

    return render(request, 'orders/merchant/order_list.html', {
        'orders':        qs,
        'status_filter': status_filter,
        'status_counts': status_counts,   # replaces broken 'counts' + 'status_choices'
        'STATUS':        Order,
    })


@merchant_required
def merchant_pending_orders(request):
    account = request.user.account
    orders  = (
        Order.objects
        .filter(merchant=account, status=Order.STATUS_PENDING)
        .select_related('customer', 'shipping_address')
        .prefetch_related('items')
        .order_by('-created_at')
    )
    return render(request, 'orders/merchant/pending_orders.html', {
        'orders': orders, 'STATUS': Order,
    })


@merchant_required
def merchant_confirmed_orders(request):
    account = request.user.account
    orders  = (
        Order.objects
        .filter(
            merchant   = account,
            status__in = [
                Order.STATUS_CONFIRMED,
                Order.STATUS_PROCESSING,
                Order.STATUS_SHIPPED,
            ],
        )
        .select_related('customer', 'shipping_address')
        .prefetch_related('items')
        .order_by('-created_at')
    )
    return render(request, 'orders/merchant/confirmed_orders.html', {
        'orders': orders, 'STATUS': Order,
    })


@merchant_required
def merchant_order_detail(request, order_id):
    account = request.user.account
    order   = get_object_or_404(
        Order.objects
        .select_related('customer', 'shipping_address')
        .prefetch_related('items', 'history', 'history__changed_by'),
        pk=order_id,
    )
    assert_merchant_owns_order(order, account)
    return render(request, 'orders/merchant/order_detail.html', {
        'order':         order,
        'next_statuses': order.merchant_next_statuses(),
        'STATUS':        Order,
    })


# ── Merchant action views (POST-only) ─────────────────────────────────────────

def _run_merchant_action(request, order_id, service_fn, success_tpl):
    """DRY wrapper for single-function merchant actions."""
    account = request.user.account
    order   = get_object_or_404(Order, pk=order_id)
    assert_merchant_owns_order(order, account)
    try:
        service_fn(order, request.user)
        messages.success(request, success_tpl.format(num=order.order_number))
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect('orders:merchant_order_detail', order_id=order_id)


@require_POST
@merchant_required
def accept_order(request, order_id):
    return _run_merchant_action(
        request, order_id, merchant_accept_order,
        "✅ Order #{num} accepted.",
    )


@require_POST
@merchant_required
def reject_order(request, order_id):
    return _run_merchant_action(
        request, order_id, merchant_reject_order,
        "❌ Order #{num} rejected. Stock restored.",
    )


@require_POST
@merchant_required
def mark_processing(request, order_id):
    return _run_merchant_action(
        request, order_id, merchant_mark_processing,
        "📦 Order #{num} marked as Processing.",
    )


@require_POST
@merchant_required
def mark_shipped(request, order_id):
    return _run_merchant_action(
        request, order_id, merchant_mark_shipped,
        "🚚 Order #{num} marked as Shipped.",
    )


@require_POST
@merchant_required
def mark_delivered(request, order_id):
    return _run_merchant_action(
        request, order_id, merchant_mark_delivered,
        "📬 Order #{num} marked as Delivered.",
    )


# ══════════════════════════════════════════════════════════════════════════════
# NOTIFICATIONS
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def notification_list(request):
    notifs = Notification.objects.filter(user=request.user).order_by('-created_at')
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return render(request, 'orders/notifications.html', {'notifications': notifs})


@require_POST
@login_required
def mark_notification_read(request, notif_id):
    notif = get_object_or_404(Notification, pk=notif_id, user=request.user)
    notif.is_read = True
    notif.save(update_fields=['is_read'])
    next_url = request.POST.get('next') or '/'
    if not url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        next_url = '/'
    return redirect(next_url)
