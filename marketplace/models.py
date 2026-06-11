"""
marketplace/models.py
=====================
Catalogue, Cart, and Wishlist models.

Order / OrderItem have been moved to the orders app.
"""

from django.db import models
from django.contrib.auth.models import User
from django.db.models import Q


# ── Catalogue ────────────────────────────────────────────────────────────────

class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    icon = models.CharField(max_length=10)
    color = models.CharField(max_length=20, default='#10B981')
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name


class Product(models.Model):
    BADGE_CHOICES = [
        ('', 'None'),
        ('New', 'New'),
        ('Popular', 'Popular'),
        ('Sale', 'Sale'),
        ('Organic', 'Organic'),
        ('Premium', 'Premium'),
    ]

    name = models.CharField(max_length=200)
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='products'
    )
    description = models.TextField()

    price = models.DecimalField(max_digits=10, decimal_places=2)
    original_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    unit = models.CharField(max_length=50)
    icon = models.CharField(max_length=10, default='🌱')

    image = models.ImageField(
        upload_to='products/',
        null=True,
        blank=True
    )

    rating = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        default=4.0
    )

    review_count = models.PositiveIntegerField(default=0)
    stock = models.PositiveIntegerField(default=100)

    badge = models.CharField(
        max_length=20,
        blank=True,
        choices=BADGE_CHOICES
    )

    suitable_crops = models.JSONField(default=list)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    merchant = models.ForeignKey(
        'accounts.UserAccount',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products',
        limit_choices_to={'role': 'merchant'},
    )

    class Meta:
        ordering = ['-review_count', '-rating']

        indexes = [
            models.Index(fields=['merchant', 'is_active']),
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['is_active', 'stock']),
        ]

        constraints = [
            models.CheckConstraint(
                condition=Q(price__gte=0),
                name='product_price_non_negative',
            ),
            models.CheckConstraint(
                condition=Q(original_price__isnull=True) |
                Q(original_price__gte=0),
                name='product_original_price_non_negative',
            ),
            models.CheckConstraint(
                condition=Q(rating__gte=0) &
                Q(rating__lte=5),
                name='product_rating_0_5',
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.category.name})"

    @property
    def discount_pct(self):
        if self.original_price and self.original_price > self.price:
            return int(round((1 - self.price / self.original_price) * 100))
        return 0

    @property
    def stars_full(self):
        return int(self.rating)

    @property
    def stars_half(self):
        return 1 if (self.rating - int(self.rating)) >= 0.5 else 0

    @property
    def stars_empty(self):
        return 5 - self.stars_full - self.stars_half

    @property
    def in_stock(self):
        return self.stock > 0


# ── Cart ─────────────────────────────────────────────────────────────────────

class Cart(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='cart'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_total(self):
        return sum(
            item.subtotal
            for item in self.items.select_related('product').all()
        )

    def get_item_count(self):
        return sum(item.quantity for item in self.items.all())

    def __str__(self):
        return f"Cart of {self.user.username} ({self.get_item_count()} items)"


class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name='items'
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE
    )

    quantity = models.PositiveIntegerField(default=1)

    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('cart', 'product')

    @property
    def subtotal(self):
        return self.product.price * self.quantity

    def __str__(self):
        return f"{self.quantity}× {self.product.name}"


# ── Wishlist ─────────────────────────────────────────────────────────────────

class Wishlist(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='wishlist'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Wishlist of {self.user.username}"


class WishlistItem(models.Model):
    wishlist = models.ForeignKey(
        Wishlist,
        on_delete=models.CASCADE,
        related_name='items'
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE
    )

    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('wishlist', 'product')
        ordering = ['-added_at']

    def __str__(self):
        return f"{self.product.name} → {self.wishlist.user.username}"


# ── Reviews ──────────────────────────────────────────────────────────────────

class ProductReview(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='reviews'
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='product_reviews'
    )

    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)

    is_verified_purchase = models.BooleanField(default=False)
    helpful_votes = models.PositiveIntegerField(default=0)

    sentiment = models.CharField(max_length=20, blank=True)

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

        constraints = [
            models.UniqueConstraint(
                fields=['product', 'user'],
                name='unique_product_review_per_user'
            ),
            models.CheckConstraint(
                condition=Q(rating__gte=1) &
                Q(rating__lte=5),
                name='product_review_rating_1_5',
            ),
        ]

        indexes = [
            models.Index(fields=['product', '-created_at']),
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return f"{self.product.name} review by {self.user.username}"