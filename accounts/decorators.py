from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.core.exceptions import PermissionDenied


# ── Standard login gate ───────────────────────────────────────────────────────

def login_required(view_func):
    """Redirect to accounts login if not authenticated."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        return view_func(request, *args, **kwargs)
    return wrapper


# Alias so existing code that imports account_login_required still works
account_login_required = login_required


# ── Role gates ────────────────────────────────────────────────────────────────

def merchant_required(view_func):
    """
    Allow only authenticated users whose account role is 'merchant'.

    Usage:
        @merchant_required
        def merchant_dashboard(request):
            pass
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        account = getattr(request.user, 'account', None)
        if not account or not account.is_merchant:
            messages.error(request, '🚫 Access denied. A Merchant account is required.')
            return redirect('accounts:user_dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def user_required(view_func):
    """
    Allow only authenticated users whose account role is 'user' (not merchant).

    Usage:
        @user_required
        def checkout(request):
            pass
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        account = getattr(request.user, 'account', None)
        if account and account.is_merchant:
            messages.info(request, 'That page is for buyers only. Redirecting to your dashboard.')
            return redirect('accounts:merchant_dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper
