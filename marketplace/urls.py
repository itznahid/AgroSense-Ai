from django.urls import path
from . import views

urlpatterns = [
    # ── Catalogue (public) ────────────────────────────────────────────────────
    path('',                   views.marketplace_view,    name='marketplace'),
  
    path('product/<int:pk>/',  views.product_detail_view, name='product_detail'),

    # ── Cart ──────────────────────────────────────────────────────────────────
    path('cart/',                          views.cart_view,        name='cart'),
    path('cart/add/<int:pk>/',             views.add_to_cart,      name='add_to_cart'),
    path('cart/update/<int:pk>/',          views.update_cart_item, name='update_cart_item'),
    path('cart/remove/<int:pk>/',          views.remove_from_cart, name='remove_from_cart'),

    # ── Checkout & orders ─────────────────────────────────────────────────────
    path('checkout/',                      views.checkout_view,    name='checkout'),
    path('orders/<int:pk>/success/',       views.order_success,    name='order_success'),

    # ── Wishlist ──────────────────────────────────────────────────────────────
    path('wishlist/toggle/<int:pk>/',      views.toggle_wishlist,  name='toggle_wishlist'),

    # ── Analytics ─────────────────────────────────────────────────────────────
    path('rec/click/',                     views.track_rec_click,  name='track_rec_click'),
]