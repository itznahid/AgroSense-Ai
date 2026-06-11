from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import reverse_lazy


class AccountLoginRequiredMixin(LoginRequiredMixin):
    """Override default login_url to point at our custom login view."""
    login_url = reverse_lazy('accounts:login')


class MerchantRequiredMixin(AccountLoginRequiredMixin):
    """
    CBV counterpart of @merchant_required.
    Must be listed before any View class in the MRO.

    Usage:
        class MerchantDashboardView(MerchantRequiredMixin, View):
            pass
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        account = getattr(request.user, 'account', None)
        if not account or not account.is_merchant:
            messages.error(request, '🚫 Access denied. A Merchant account is required.')
            return redirect('accounts:user_dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_merchant_context(self):
        """Convenience helper – returns (account, merchant_profile) tuple."""
        account = self.request.user.account
        return account, getattr(account, 'merchant_profile', None)


class UserRequiredMixin(AccountLoginRequiredMixin):
    """
    CBV counterpart of @user_required.
    Bounces merchants to their own dashboard.

    Usage:
        class CheckoutView(UserRequiredMixin, View):
            pass
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        account = getattr(request.user, 'account', None)
        if account and account.is_merchant:
            messages.info(request, 'That page is for buyers only. Redirecting to your dashboard.')
            return redirect('accounts:merchant_dashboard')
        return super().dispatch(request, *args, **kwargs)


class OwnershipMixin:
    """
    Mixin that enforces object-level ownership on any view that resolves
    a pk from the URL.  Override get_owner_field to customise the lookup.

    Default behaviour: requires ``obj.shop.owner == request.user``
    (aligned to the spec).  Raises PermissionDenied for non-owners.
    """

    owner_field = 'merchant__user'  # Django ORM double-underscore path

    def check_ownership(self, obj, user):
        """
        Return True if the requesting user owns the object.
        Override for custom logic.
        """
        account = getattr(user, 'account', None)
        # Works for Product.merchant == UserAccount
        if hasattr(obj, 'merchant') and obj.merchant == account:
            return True
        # Works for MerchantProfile.account == UserAccount
        if hasattr(obj, 'account') and obj.account == account:
            return True
        return False

    def raise_if_not_owner(self, obj, user):
        if not self.check_ownership(obj, user):
            raise PermissionDenied
