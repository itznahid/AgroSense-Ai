from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # ── Auth ──────────────────────────────────────────────────────────────────
    path('',           views.login_view,    name='login'),
    path('register/',  views.register_view, name='register'),
    path('login/',     views.login_view,    name='login'),
    path('logout/',    views.logout_view,   name='logout'),

    # ══════════════════════════════════════════════════════════════════════════
    # USER DASHBOARD  (/dashboard/*)
    # ══════════════════════════════════════════════════════════════════════════
    path('dashboard/',                     views.UserDashboardView.as_view(),  name='user_dashboard'),
    # These two now redirect to orders:my_orders / orders:order_detail
    # so that existing nav links ({% url 'accounts:user_orders' %}) keep working.
    path('dashboard/orders/',              views.UserOrderListView.as_view(),  name='user_orders'),
    path('dashboard/orders/<pk>/',         views.UserOrderDetailView.as_view(),name='user_order_detail'),
    path('dashboard/wishlist/',            views.UserWishlistView.as_view(),   name='user_wishlist'),
    path('dashboard/profile/',             views.UserProfileView.as_view(),    name='user_profile'),
    path('dashboard/settings/',            views.UserSettingsView.as_view(),   name='user_settings'),

    # ══════════════════════════════════════════════════════════════════════════
    # MERCHANT DASHBOARD  (/merchant/*)
    # ══════════════════════════════════════════════════════════════════════════
    path('merchant/dashboard/',            views.MerchantDashboardView.as_view(),  name='merchant_dashboard'),

    # ── Shop ──────────────────────────────────────────────────────────────────
    path('merchant/shop/',                 views.MerchantShopView.as_view(),    name='merchant_shop'),
    path('merchant/shop/edit/',            views.ShopEditView.as_view(),        name='merchant_shop_edit'),

    # ── Products ──────────────────────────────────────────────────────────────
    path('merchant/shop/add/',             views.ProductCreateView.as_view(),   name='add_product'),
    path('merchant/shop/<int:pk>/edit/',   views.ProductUpdateView.as_view(),   name='edit_product'),
    path('merchant/shop/<int:pk>/delete/', views.ProductDeleteView.as_view(),   name='delete_product'),

    # ── Orders — these redirect to the orders app ─────────────────────────────
    # Kept so that any hardcoded {% url 'accounts:merchant_orders' %} links
    # in existing templates continue to work without a template change.
    path('merchant/orders/',               views.MerchantOrderListView.as_view(),    name='merchant_orders'),
    path('merchant/orders/<int:pk>/update/', views.MerchantOrderUpdateView.as_view(), name='merchant_order_update'),

    # ── Analytics & Inventory ─────────────────────────────────────────────────
    path('merchant/analytics/',            views.MerchantAnalyticsView.as_view(),  name='merchant_analytics'),
    path('merchant/inventory/',            views.MerchantInventoryView.as_view(),  name='merchant_inventory'),
]
