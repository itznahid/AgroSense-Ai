from django.contrib import admin
from .models import Category, Product, Cart, CartItem, Wishlist, WishlistItem, ProductReview


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display        = ('icon', 'name', 'slug', 'order')
    prepopulated_fields = {'slug': ('name',)}
    ordering            = ('order',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display    = ('icon', 'name', 'category', 'merchant', 'price', 'stock', 'badge', 'is_active')
    list_filter     = ('category', 'badge', 'is_active', 'merchant')
    search_fields   = ('name', 'description')
    list_editable   = ('price', 'stock', 'is_active')
    ordering        = ('-review_count',)
    readonly_fields = ('created_at',)

    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'icon', 'category', 'merchant', 'description', 'is_active')
        }),
        ('Pricing & Stock', {
            'fields': ('price', 'original_price', 'unit', 'stock', 'badge')
        }),
        ('Ratings', {
            'fields': ('rating', 'review_count')
        }),
        ('Crop Suitability', {
            'fields': ('suitable_crops',),
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        }),
    )


class CartItemInline(admin.TabularInline):
    model      = CartItem
    extra      = 0
    raw_id_fields = ('product',)


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_item_count', 'updated_at')
    inlines      = [CartItemInline]

    @admin.display(description='Items')
    def get_item_count(self, obj):
        return obj.get_item_count()


class WishlistItemInline(admin.TabularInline):
    model         = WishlistItem
    extra         = 0
    raw_id_fields = ('product',)


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at')
    inlines      = [WishlistItemInline]


@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'rating', 'is_verified_purchase', 'helpful_votes', 'created_at')
    list_filter = ('rating', 'is_verified_purchase', 'created_at')
    search_fields = ('product__name', 'user__username', 'user__email', 'comment')
    raw_id_fields = ('product', 'user')
    readonly_fields = ('created_at', 'updated_at')
