from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import TemplateView

from .decorators import login_required as account_login_required, merchant_required
from .forms import (
    MerchantProductForm, MerchantRegisterForm, ShopEditForm,
    UserProfileForm, UserRegisterForm,
)
from .mixins import AccountLoginRequiredMixin, MerchantRequiredMixin, UserRequiredMixin
from .models import MerchantProfile, UserAccount

from marketplace.models import Product, Category, Wishlist, WishlistItem
from orders.models import Notification, Order


# ── Helpers ───────────────────────────────────────────────────────────────────

def _redirect_by_role(user):
    account = getattr(user, 'account', None)
    if account and account.is_merchant:
        return redirect('accounts:merchant_dashboard')
    return redirect('accounts:user_dashboard')


# ══════════════════════════════════════════════════════════════════════════════
# AUTH
# ══════════════════════════════════════════════════════════════════════════════

def login_view(request):
    if request.user.is_authenticated:
        return _redirect_by_role(request.user)

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user     = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return _redirect_by_role(user)
        messages.error(request, 'Invalid username or password.')

    # FIX: was 'accounts/login.html' — templates live in account/ (singular)
    return render(request, 'account/login.html')


def register_view(request):
    if request.user.is_authenticated:
        return _redirect_by_role(request.user)

    # FIX: role was never derived or passed to template; both forms were
    # instantiated simultaneously, and merchant_form had no shop fields so
    # cleaned_data['shop_name'] raised KeyError on submission.
    # Now: pick role → pick one form class → pass as 'form' + 'role'.
    role = request.POST.get('role') or request.GET.get('role', 'user')
    if role not in ('user', 'merchant'):
        role = 'user'

    FormClass = MerchantRegisterForm if role == 'merchant' else UserRegisterForm
    form = FormClass(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        user    = form.save()
        account = UserAccount.objects.create(
            user  = user,
            role  = role,
            phone = form.cleaned_data.get('phone', ''),
        )
        if role == 'merchant':
            MerchantProfile.objects.create(
                account          = account,
                shop_name        = form.cleaned_data['shop_name'],
                shop_icon        = form.cleaned_data.get('shop_icon', '🏪'),
                shop_description = form.cleaned_data.get('shop_description', ''),
            )
            login(request, user)
            messages.success(request, f"Welcome, {user.username}! Your merchant account is ready.")
            return redirect('accounts:merchant_dashboard')
        else:
            login(request, user)
            messages.success(request, f"Welcome to AgroSense, {user.username}!")
            return redirect('accounts:user_dashboard')

    # FIX: was 'accounts/register.html'
    return render(request, 'account/register.html', {
        'form': form,
        'role': role,
    })


def logout_view(request):
    logout(request)
    return redirect('accounts:login')


# ══════════════════════════════════════════════════════════════════════════════
# USER DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

class UserDashboardView(AccountLoginRequiredMixin, View):
    def get(self, request):
        account = getattr(request.user, 'account', None)
        if account and account.is_merchant:
            return redirect('accounts:merchant_dashboard')

        pred_count  = 0
        predictions = []
        try:
            from recommend.models import UserProfile, Prediction
            profile, _ = UserProfile.objects.get_or_create(
                user=request.user,
                defaults={'phone': '', 'language': 'en'},
            )
            predictions = Prediction.objects.filter(user=profile).order_by('-created_at')[:5]
            pred_count  = Prediction.objects.filter(user=profile).count()
        except Exception:
            pass

        recent_orders = (
            Order.objects
            .filter(customer=request.user)
            .select_related('merchant', 'merchant__merchant_profile')
            .order_by('-created_at')[:5]
        )

        unread_notifs = Notification.objects.filter(
            user=request.user, is_read=False
        ).count()

        # FIX: was 'accounts/user_dashboard.html'
        return render(request, 'account/user_dashboard.html', {
            'account':        account,
            'predictions':    predictions,
            'pred_count':     pred_count,
            'recent_orders':  recent_orders,
            'unread_notifs':  unread_notifs,
        })


class UserOrderListView(AccountLoginRequiredMixin, View):
    """Redirect to the orders app's comprehensive order list."""
    def get(self, request):
        return redirect('orders:my_orders')


class UserOrderDetailView(AccountLoginRequiredMixin, View):
    """Redirect to the orders app's order detail."""
    def get(self, request, pk):
        return redirect('orders:order_detail', order_id=pk)


class UserWishlistView(AccountLoginRequiredMixin, View):
    def get(self, request):
        account = getattr(request.user, 'account', None)
        wishlist, _ = Wishlist.objects.get_or_create(user=request.user)
        items = wishlist.items.select_related('product', 'product__category').all()
        # FIX: was 'accounts/user_wishlist.html'
        return render(request, 'account/user_wishlist.html', {
            'account':  account,
            'wishlist': wishlist,
            'items':    items,
        })


class UserProfileView(UserRequiredMixin, View):
    def get(self, request):
        account = getattr(request.user, 'account', None)
        # FIX: pass phone initial so form.phone.value() renders correctly in template
        initial = {'phone': account.phone if account else ''}
        form    = UserProfileForm(instance=request.user, initial=initial)
        # FIX: was 'accounts/user_profile.html'
        return render(request, 'account/user_profile.html', {
            'account': account, 'form': form,
        })

    def post(self, request):
        account = getattr(request.user, 'account', None)
        form    = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            # FIX: phone lives on UserAccount, not the User model — save it separately
            phone = form.cleaned_data.get('phone', '')
            if account:
                account.phone = phone
                account.save(update_fields=['phone'])
            messages.success(request, 'Profile updated.')
            return redirect('accounts:user_profile')
        # FIX: was 'accounts/user_profile.html'
        return render(request, 'account/user_profile.html', {
            'account': account, 'form': form,
        })


class UserSettingsView(UserRequiredMixin, TemplateView):
    # FIX: was 'accounts/user_settings.html'
    template_name = 'account/user_settings.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['account'] = getattr(self.request.user, 'account', None)
        return ctx


# ══════════════════════════════════════════════════════════════════════════════
# MERCHANT DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

class MerchantDashboardView(MerchantRequiredMixin, View):
    def get(self, request):
        account, merchant_profile = self.get_merchant_context()

        products        = Product.objects.filter(merchant=account)
        active_products = products.filter(is_active=True)

        merchant_orders = Order.objects.filter(merchant=account)
        total_orders    = merchant_orders.count()
        pending_orders  = merchant_orders.filter(status=Order.STATUS_PENDING).count()

        from django.db.models import Sum
        revenue = (
            merchant_orders
            .exclude(status__in=[Order.STATUS_CANCELLED, Order.STATUS_REJECTED])
            .aggregate(total=Sum('subtotal'))['total'] or 0
        )

        recent_orders = (
            merchant_orders
            .select_related('customer', 'shipping_address')
            .prefetch_related('items')
            .order_by('-created_at')[:5]
        )

        low_stock = [p for p in active_products if 0 < p.stock < 10]

        unread_notifs = Notification.objects.filter(
            user=request.user, is_read=False
        ).count()

        # FIX: was 'accounts/merchant_dashboard.html'
        return render(request, 'account/merchant_dashboard.html', {
            'account':          account,
            'merchant_profile': merchant_profile,
            'total_products':   products.count(),
            'active_products':  active_products.count(),
            'total_stock':      sum(p.stock for p in active_products),
            'recent_products':  products.order_by('-created_at')[:5],
            'total_orders':     total_orders,
            'pending_orders':   pending_orders,
            'revenue':          revenue,
            'recent_orders':    recent_orders,
            'low_stock':        low_stock,
            'unread_notifs':    unread_notifs,
        })


# ── Shop management ───────────────────────────────────────────────────────────

class MerchantShopView(MerchantRequiredMixin, View):
    def get(self, request):
        account, merchant_profile = self.get_merchant_context()

        # FIX: cat_filter and categories were never passed; category filter UI
        # rendered no options and filtering never applied
        cat_filter = request.GET.get('cat', '')
        products   = Product.objects.filter(merchant=account).select_related('category')
        if cat_filter:
            products = products.filter(category__slug=cat_filter)
        categories = Category.objects.all()

        # FIX: was 'accounts/merchant_shop.html'
        return render(request, 'account/merchant_shop.html', {
            'account':          account,
            'merchant_profile': merchant_profile,
            'products':         products,
            'categories':       categories,
            'cat_filter':       cat_filter,
        })


class ShopEditView(MerchantRequiredMixin, View):
    def get(self, request):
        account, merchant_profile = self.get_merchant_context()
        form = ShopEditForm(instance=merchant_profile)
        # FIX: was 'accounts/merchant_shop_edit.html'
        return render(request, 'account/merchant_shop_edit.html', {
            'account':          account,
            'merchant_profile': merchant_profile,
            'form':             form,
        })

    def post(self, request):
        account, merchant_profile = self.get_merchant_context()
        form = ShopEditForm(request.POST, request.FILES, instance=merchant_profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Shop details updated.')
            return redirect('accounts:merchant_shop')
        # FIX: was 'accounts/merchant_shop_edit.html'
        return render(request, 'account/merchant_shop_edit.html', {
            'account':          account,
            'merchant_profile': merchant_profile,
            'form':             form,
        })


# ── Product CRUD ──────────────────────────────────────────────────────────────

class ProductCreateView(MerchantRequiredMixin, View):
    def get(self, request):
        account, merchant_profile = self.get_merchant_context()
        # FIX: was 'accounts/product_form.html'
        return render(request, 'account/product_form.html', {
            'form': MerchantProductForm(), 'account': account,
            'merchant_profile': merchant_profile, 'action': 'Add',
        })

    def post(self, request):
        account, merchant_profile = self.get_merchant_context()
        form = MerchantProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.merchant = account
            product.save()
            messages.success(request, f"'{product.name}' added to your shop.")
            return redirect('accounts:merchant_shop')
        # FIX: was 'accounts/product_form.html'
        return render(request, 'account/product_form.html', {
            'form': form, 'account': account,
            'merchant_profile': merchant_profile, 'action': 'Add',
        })


class ProductUpdateView(MerchantRequiredMixin, View):
    def _get_product(self, pk, account):
        return get_object_or_404(Product, pk=pk, merchant=account)

    def get(self, request, pk):
        account, merchant_profile = self.get_merchant_context()
        product = self._get_product(pk, account)
        # FIX: was 'accounts/product_form.html'
        return render(request, 'account/product_form.html', {
            'form': MerchantProductForm(instance=product), 'account': account,
            'merchant_profile': merchant_profile, 'action': 'Edit',
            'product': product,
        })

    def post(self, request, pk):
        account, merchant_profile = self.get_merchant_context()
        product = self._get_product(pk, account)
        form = MerchantProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, f"'{product.name}' updated.")
            return redirect('accounts:merchant_shop')
        # FIX: was 'accounts/product_form.html'
        return render(request, 'account/product_form.html', {
            'form': form, 'account': account,
            'merchant_profile': merchant_profile, 'action': 'Edit',
            'product': product,
        })


class ProductDeleteView(MerchantRequiredMixin, View):
    # FIX: GET handler was missing entirely — clicking the delete link in
    # merchant_shop.html hit this URL with GET and got a 405 Method Not Allowed.
    # Added GET to render the confirmation page.
    def get(self, request, pk):
        account, merchant_profile = self.get_merchant_context()
        product = get_object_or_404(Product, pk=pk, merchant=account)
        return render(request, 'account/confirm_delete.html', {
            'account':          account,
            'merchant_profile': merchant_profile,
            'product':          product,
        })

    def post(self, request, pk):
        account, _ = self.get_merchant_context()
        product    = get_object_or_404(Product, pk=pk, merchant=account)
        name       = product.name
        product.delete()
        messages.success(request, f"'{name}' deleted.")
        return redirect('accounts:merchant_shop')


# ── Merchant orders → delegates to orders app ─────────────────────────────────

class MerchantOrderListView(MerchantRequiredMixin, View):
    """Redirect to the orders app's full-featured merchant order list."""
    def get(self, request):
        return redirect('orders:merchant_order_list')


class MerchantOrderUpdateView(MerchantRequiredMixin, View):
    """Legacy endpoint — no longer used. Redirect to orders app."""
    def post(self, request, pk):
        return redirect('orders:merchant_order_list')


# ── Analytics ─────────────────────────────────────────────────────────────────

class MerchantAnalyticsView(MerchantRequiredMixin, View):
    def get(self, request):
        account, merchant_profile = self.get_merchant_context()

        from django.db.models import Sum
        merchant_orders = (
            Order.objects
            .filter(merchant=account)
            .exclude(status__in=[Order.STATUS_CANCELLED, Order.STATUS_REJECTED])
            .select_related('customer')
            .prefetch_related('items')
        )
        total_revenue = merchant_orders.aggregate(t=Sum('subtotal'))['t'] or 0
        total_orders  = merchant_orders.count()
        products      = Product.objects.filter(merchant=account)

        # FIX: was 'accounts/merchant_analytics.html'
        return render(request, 'account/merchant_analytics.html', {
            'account':          account,
            'merchant_profile': merchant_profile,
            'total_revenue':    total_revenue,
            'total_orders':     total_orders,
            'products':         products,
            # FIX: template was checking 'recent_items' (old OrderItem var) — renamed to 'recent_orders'
            'recent_orders':    merchant_orders.order_by('-created_at')[:20],
        })


# ── Inventory ─────────────────────────────────────────────────────────────────

class MerchantInventoryView(MerchantRequiredMixin, View):
    def get(self, request):
        account, merchant_profile = self.get_merchant_context()
        # FIX: sort by stock ascending so lowest-stock items appear first (as doc'd in template)
        products = (
            Product.objects
            .filter(merchant=account)
            .select_related('category')
            .order_by('stock')
        )

        # FIX: out_of_stock and low_stock_items were never passed; alert banners
        # in the template were always hidden
        out_of_stock     = [p for p in products if p.stock == 0]
        low_stock_items  = [p for p in products if 0 < p.stock < 10]

        # FIX: was 'accounts/merchant_inventory.html'
        return render(request, 'account/merchant_inventory.html', {
            'account':          account,
            'merchant_profile': merchant_profile,
            'products':         products,
            'out_of_stock':     out_of_stock,
            'low_stock_items':  low_stock_items,
        })

    def post(self, request):
        """Bulk-update stock levels."""
        account, _ = self.get_merchant_context()
        for key, value in request.POST.items():
            if key.startswith('stock_'):
                try:
                    pk    = int(key.split('_')[1])
                    stock = int(value)
                    Product.objects.filter(pk=pk, merchant=account).update(stock=max(0, stock))
                except (ValueError, IndexError):
                    pass
        messages.success(request, 'Inventory updated.')
        return redirect('accounts:merchant_inventory')
