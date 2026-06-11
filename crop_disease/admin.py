from django.contrib import admin
from django.utils.html import format_html
from .models import CropDiseaseScan


@admin.register(CropDiseaseScan)
class CropDiseaseScanAdmin(admin.ModelAdmin):
    list_display  = (
        "id", "user", "thumbnail", "crop_name", "predicted_class",
        "confidence", "severity_colored", "is_healthy", "status", "uploaded_at",
    )
    list_filter   = ("status", "is_healthy", "severity")
    search_fields = ("predicted_class", "crop_name", "user__username", "user__email")
    # FIX: marketplace_products and product_narrative were missing from
    # readonly_fields, so Django rendered them as raw editable JSON/text
    # widgets in the change form instead of read-only displays.
    readonly_fields = (
        "thumbnail", "uploaded_at",
        "crop_name", "predicted_class", "confidence", "severity",
        "is_healthy", "symptoms", "causes", "treatment_steps",
        "prevention_tips", "additional_notes",
        "marketplace_products", "product_narrative",
        "status", "error_message",
    )
    ordering = ("-uploaded_at",)

    def thumbnail(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height:60px;border-radius:4px;" />',
                obj.image.url,
            )
        return "—"
    thumbnail.short_description = "Image"

    def severity_colored(self, obj):
        colors = {
            "Critical": "#dc3545",
            "High":     "#fd7e14",
            "Moderate": "#0dcaf0",
            "Low":      "#6c757d",
            "None":     "#198754",
        }
        color = colors.get(obj.severity, "#343a40")
        return format_html(
            '<span style="color:{};font-weight:600;">{}</span>',
            color,
            obj.severity or "—",
        )
    severity_colored.short_description = "Severity"
