"""
marketplace/views.py
====================
Catalogue browsing, cart, wishlist, and smart recommendations.

Checkout has moved to the  orders  app.
The  checkout  URL now issues a permanent redirect for backward
compatibility so any bookmarked /checkout/ links still work.
"""

import math

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from accounts.decorators import (
    login_required as account_login_required,
    merchant_required,
    user_required,
)

from .models import Cart, CartItem, Category, Product, Wishlist, WishlistItem


# ── Smart recommendations ─────────────────────────────────────────────────────

CROP_AFFINITY = {
    'rice':    ['fertilizer', 'pesticide', 'seed', 'irrigation'],
    'wheat':   ['fertilizer', 'seed', 'harvesting'],
    'jute':    ['fertilizer', 'pesticide', 'soil'],
    'potato':  ['fertilizer', 'pesticide', 'storage'],
    'mango':   ['fertilizer', 'pesticide', 'pruning'],
    'default': ['fertilizer', 'seed', 'pesticide', 'tool'],
}


def _score_product(product, crop_lower: str, affinity_slugs: list) -> float:
    score = 0.0
    cat_slug = getattr(product.category, 'slug', '')
    for slug in affinity_slugs:
        if slug in cat_slug:
            score += 3.0
            break
    name_lower = product.name.lower()
    if crop_lower and crop_lower in name_lower:
        score += 2.0
    crops = product.suitable_crops or []
    if isinstance(crops, list):
        for c in crops:
            if crop_lower and crop_lower in str(c).lower():
                score += 2.0
                break
    score += float(product.rating) * 0.5
    score += math.log1p(product.review_count) * 0.3
    return score


def get_smart_recommendations(crop_name, limit=20):
    crop_lower     = (crop_name or '').lower().strip()
    affinity_slugs = CROP_AFFINITY.get(crop_lower, CROP_AFFINITY['default'])
    qs = (
        Product.objects
        .filter(is_active=True, stock__gt=0)
        .select_related('category', 'merchant')
        .order_by('-review_count', '-rating')[:80]
    )
    scored = [(p, _score_product(p, crop_lower, affinity_slugs)) for p in qs]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [p for p, _ in scored[:limit]]


def get_recommended_products(crop_name, limit=6):
    return get_smart_recommendations(crop_name, limit=limit)


def track_rec_click(request):
    return redirect('marketplace')


# ── Catalogue ─────────────────────────────────────────────────────────────────

def marketplace_view(request):
    crop_name = ''
    try:
        from recommend.models import UserProfile
        if request.user.is_authenticated:
            profile, _ = UserProfile.objects.get_or_create(
                user=request.user,
                defaults={'phone': '', 'language': 'en'},
            )
            crop_name = profile.primary_crop or ''
    except Exception:
        pass

    # Annotate categories with active product count for {{ cat.product_count }}
    categories = Category.objects.annotate(
        product_count=Count('products', filter=Q(products__is_active=True))
    )

    selected_cat = request.GET.get('category', '').strip()
    query        = request.GET.get('q', '').strip()
    sort         = request.GET.get('sort', '').strip()

    all_count = Product.objects.filter(is_active=True).count()

    # Always start with the full active queryset; apply filters independently
    products = (
        Product.objects
        .filter(is_active=True)
        .select_related('category', 'merchant', 'merchant__merchant_profile')
    )

    if selected_cat and selected_cat.lower() != 'all':
        products = products.filter(category__slug=selected_cat)

    if query:
        products = products.filter(name__icontains=query)

    if sort == 'price_asc':
        products = products.order_by('price')
    elif sort == 'price_desc':
        products = products.order_by('-price')
    elif sort == 'rating':
        products = products.order_by('-rating')
    elif sort == 'newest':
        products = products.order_by('-created_at')
    else:
        products = products.order_by('-review_count', '-rating')

    recommended = []
    if crop_name and not query and not selected_cat:
        recommended = get_recommended_products(crop_name, limit=6)

    total_count = products.count()

    wishlist_ids: set = set()
    if request.user.is_authenticated:
        wishlist_ids = set(
            WishlistItem.objects
            .filter(wishlist__user=request.user)
            .values_list('product_id', flat=True)
        )

    products = Paginator(products, 24).get_page(request.GET.get('page'))

    active_category = None
    if selected_cat:
        active_category = Category.objects.filter(slug=selected_cat).first()

    return render(request, 'marketplace/marketplace.html', {
        'categories':      categories,
        'products':        products,
        'recommended':     recommended,
        'wishlist_ids':    wishlist_ids,
        'selected_cat':    selected_cat,
        'active_category': active_category,
        'search_q':        query,
        'sort_by':         sort,
        'crop_filter':     crop_name,
        'all_count':       all_count,
        'total_count':     total_count,
    })


def product_detail_view(request, pk):
    product = get_object_or_404(Product, pk=pk, is_active=True)

    in_wishlist = False
    in_cart     = False
    if request.user.is_authenticated:
        in_wishlist = WishlistItem.objects.filter(
            wishlist__user=request.user, product=product
        ).exists()
        in_cart = CartItem.objects.filter(
            cart__user=request.user, product=product
        ).exists()

    related = (
        Product.objects
        .filter(category=product.category, is_active=True)
        .exclude(pk=pk)
        .order_by('-rating')[:4]
    )

    return render(request, 'marketplace/product_detail.html', {
        'product':     product,
        'related':     related,
        'in_wishlist': in_wishlist,
        'in_cart':     in_cart,
    })


# ── Cart ──────────────────────────────────────────────────────────────────────

def _get_or_create_cart(user):
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


@account_login_required
def cart_view(request):
    cart  = _get_or_create_cart(request.user)
    items = cart.items.select_related('product', 'product__category').all()
    return render(request, 'marketplace/cart.html', {'cart': cart, 'items': items})


@account_login_required
def add_to_cart(request, pk):
    product = get_object_or_404(Product, pk=pk, is_active=True)

    if not product.in_stock:
        messages.error(request, f"'{product.name}' is out of stock.")
        return _cart_redirect(request)

    cart = _get_or_create_cart(request.user)
    item, created = CartItem.objects.get_or_create(cart=cart, product=product)

    if not created:
        if item.quantity < product.stock:
            item.quantity += 1
            item.save()
            messages.success(request, f"Updated quantity for '{product.name}'.")
        else:
            messages.warning(
                request,
                f"Cannot add more '{product.name}' – stock limit reached.",
            )
    else:
        messages.success(request, f"🛒 '{product.name}' added to cart.")

    return _cart_redirect(request)


@account_login_required
def update_cart_item(request, pk):
    item = get_object_or_404(CartItem, pk=pk, cart__user=request.user)
    try:
        qty = int(request.POST.get('quantity', 1))
    except (ValueError, TypeError):
        qty = 1

    if qty < 1:
        item.delete()
        messages.info(request, f"'{item.product.name}' removed from cart.")
    elif qty > item.product.stock:
        messages.warning(request, f"Only {item.product.stock} units available.")
        item.quantity = item.product.stock
        item.save()
    else:
        item.quantity = qty
        item.save()

    return redirect('cart')


@account_login_required
def remove_from_cart(request, pk):
    item = get_object_or_404(CartItem, pk=pk, cart__user=request.user)
    name = item.product.name
    item.delete()
    messages.info(request, f"'{name}' removed from cart.")
    return redirect('cart')


def _cart_redirect(request):
    next_url = request.POST.get('next') or request.GET.get('next', '')
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    product_pk = request.POST.get('product_pk') or request.GET.get('product_pk')
    if product_pk:
        try:
            return redirect('product_detail', pk=int(product_pk))
        except (ValueError, TypeError):
            pass
    return redirect('cart')


# ── Checkout → orders app ─────────────────────────────────────────────────────

def checkout_view(request):
    return redirect('orders:checkout', permanent=False)


def order_success(request, pk):
    return redirect('orders:my_orders')


# ── Wishlist ──────────────────────────────────────────────────────────────────

@account_login_required
def toggle_wishlist(request, pk):
    product  = get_object_or_404(Product, pk=pk, is_active=True)
    wishlist, _ = Wishlist.objects.get_or_create(user=request.user)

    item = wishlist.items.filter(product=product).first()
    if item:
        item.delete()
        messages.info(request, f"'{product.name}' removed from your wishlist.")
    else:
        WishlistItem.objects.create(wishlist=wishlist, product=product)
        messages.success(request, f"❤️ '{product.name}' added to your wishlist.")

    next_url = request.POST.get('next') or request.GET.get('next', '')
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect('product_detail', pk=pk)