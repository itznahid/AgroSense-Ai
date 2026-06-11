from django.contrib import admin

from .models import Notification, Order, OrderItem, OrderStatusHistory, ShippingAddress


# ── Inlines ───────────────────────────────────────────────────────────────────

class OrderItemInline(admin.TabularInline):
    model           = OrderItem
    extra           = 0
    readonly_fields = ('product', 'product_name_snapshot', 'product_price_snapshot',
                       'quantity', 'total_price')
    can_delete      = False


class ShippingAddressInline(admin.StackedInline):
    model      = ShippingAddress
    extra      = 0
    can_delete = False
    readonly_fields = ('full_name', 'phone', 'district', 'area', 'full_address')


class OrderStatusHistoryInline(admin.TabularInline):
    model           = OrderStatusHistory
    extra           = 0
    can_delete      = False
    readonly_fields = ('previous_status', 'new_status', 'changed_by', 'timestamp')


# ── ModelAdmin ────────────────────────────────────────────────────────────────

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display    = ('order_number', 'customer', 'merchant', 'status',
                       'total_amount', 'created_at')
    list_filter     = ('status', 'created_at')
    search_fields   = ('order_number', 'customer__username',
                       'merchant__merchant_profile__shop_name')
    readonly_fields = ('id', 'order_number', 'subtotal', 'shipping_cost',
                       'tax', 'total_amount', 'created_at', 'updated_at')
    ordering        = ('-created_at',)
    inlines         = [OrderItemInline, ShippingAddressInline,
                       OrderStatusHistoryInline]

    fieldsets = (
        ('Identifiers', {'fields': ('id', 'order_number')}),
        ('Parties', {'fields': ('customer', 'merchant')}),
        ('Status', {'fields': ('status',)}),
        ('Financials', {'fields': ('subtotal', 'shipping_cost', 'tax', 'total_amount')}),
        ('Notes', {'fields': ('notes',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display  = ('user', 'message', 'is_read', 'created_at')
    list_filter   = ('is_read', 'created_at')
    search_fields = ('user__username', 'message')
    readonly_fields = ('user', 'message', 'created_at')
