"""
orders/permissions.py
=====================
Lightweight permission helpers.  Views call these instead of doing
inline checks so the ownership logic lives in one place.
"""

from django.core.exceptions import PermissionDenied


# ── Customer ownership ────────────────────────────────────────────────────────

def assert_customer_owns_order(order, user) -> None:
    """Raise PermissionDenied if *user* is not the order's customer."""
    if order.customer_id != user.pk:
        raise PermissionDenied("You do not own this order.")


def customer_owns_order(order, user) -> bool:
    return order.customer_id == user.pk


# ── Merchant ownership ────────────────────────────────────────────────────────

def assert_merchant_owns_order(order, merchant_account) -> None:
    """Raise PermissionDenied if *merchant_account* did not receive this order."""
    if order.merchant_id != merchant_account.pk:
        raise PermissionDenied("This order does not belong to your shop.")


def merchant_owns_order(order, merchant_account) -> bool:
    return order.merchant_id == merchant_account.pk


# ── Action guards (return bool, no exceptions) ────────────────────────────────

def customer_can_cancel(order, user) -> bool:
    return customer_owns_order(order, user) and order.is_cancellable_by_customer


def customer_can_confirm_delivery(order, user) -> bool:
    return customer_owns_order(order, user) and order.is_confirmable_by_customer


def merchant_can_reject(order, merchant_account) -> bool:
    return merchant_owns_order(order, merchant_account) and order.is_rejectable_by_merchant
