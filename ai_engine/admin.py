"""
ai_engine/admin.py — Django Admin for AI Engine models
Provides UI for managing Gemini keys, viewing call logs, and digital twins.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Avg
from .models import AIKeyConfig, AICallLog, DigitalTwin, MerchantTwin


@admin.register(AIKeyConfig)
class AIKeyConfigAdmin(admin.ModelAdmin):
    list_display  = ["name", "priority", "masked_key_display", "is_active", "last_used_at", "success_rate_display"]
    list_filter   = ["is_active", "priority"]
    list_editable = ["priority", "is_active"]
    ordering      = ["priority"]
    readonly_fields = ["last_used_at"]

    fieldsets = [
        ("Key Identity", {"fields": ["name", "api_key", "priority", "is_active"]}),
        ("Metadata",     {"fields": ["notes", "last_used_at"]}),
    ]

    def masked_key_display(self, obj):
        return obj.masked_key()
    masked_key_display.short_description = "API Key"

    def success_rate_display(self, obj):
        rate = obj.success_rate()
        color = "green" if rate >= 95 else "orange" if rate >= 80 else "red"
        return format_html('<span style="color:{}">{:.1f}%</span>', color, rate)
    success_rate_display.short_description = "Success Rate"


@admin.register(AICallLog)
class AICallLogAdmin(admin.ModelAdmin):
    list_display  = ["timestamp", "model_used", "agent_type", "success_icon", "latency_ms", "is_failover", "error_type"]
    list_filter   = ["success", "model_used", "agent_type", "is_failover"]
    readonly_fields = [f.name for f in AICallLog._meta.fields]
    ordering      = ["-timestamp"]
    date_hierarchy = "timestamp"

    def success_icon(self, obj):
        return format_html("✅" if obj.success else "❌")
    success_icon.short_description = "Status"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(DigitalTwin)
class DigitalTwinAdmin(admin.ModelAdmin):
    list_display  = ["user", "total_orders", "budget_range", "purchase_frequency", "last_updated"]
    list_filter   = ["budget_range", "purchase_frequency"]
    readonly_fields = ["last_updated", "ai_profile"]
    search_fields = ["user__username", "user__email"]
    actions       = ["rebuild_twins"]

    def rebuild_twins(self, request, queryset):
        count = 0
        for twin in queryset:
            twin.rebuild()
            count += 1
        self.message_user(request, f"Rebuilt {count} digital twin(s).")
    rebuild_twins.short_description = "Rebuild selected Digital Twins"


@admin.register(MerchantTwin)
class MerchantTwinAdmin(admin.ModelAdmin):
    list_display  = ["merchant", "total_revenue", "total_orders_served", "last_updated"]
    readonly_fields = ["last_updated", "analytics_cache"]
    actions = ["rebuild_twins"]

    def rebuild_twins(self, request, queryset):
        count = 0
        for twin in queryset:
            twin.rebuild()
            count += 1
        self.message_user(request, f"Rebuilt {count} merchant twin(s).")
    rebuild_twins.short_description = "Rebuild selected Merchant Twins"
