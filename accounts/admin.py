from django.contrib import admin
from .models import UserAccount, MerchantProfile


@admin.register(UserAccount)
class UserAccountAdmin(admin.ModelAdmin):
    list_display    = ('user', 'role', 'phone', 'created_at')
    list_filter     = ('role',)
    search_fields   = ('user__username', 'user__email', 'phone')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(MerchantProfile)
class MerchantProfileAdmin(admin.ModelAdmin):
    list_display    = ('shop_icon', 'shop_name', 'account', 'is_verified', 'created_at')
    list_filter     = ('is_verified',)
    search_fields   = ('shop_name', 'account__user__username')
    list_editable   = ('is_verified',)
    readonly_fields = ('created_at',)
    fieldsets = (
        ('Shop Info', {
            'fields': ('account', 'shop_name', 'shop_description', 'shop_icon', 'logo'),
        }),
        ('Status', {
            'fields': ('is_verified', 'created_at'),
        }),
    )
