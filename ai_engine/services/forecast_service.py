"""
forecast_service.py — Demand & Revenue Forecasting Service
Uses historical sales patterns to build forecast inputs for Gemini.
"""
from __future__ import annotations
import logging
from django.db.models import Sum, Count, F, ExpressionWrapper, DecimalField
from django.db.models.functions import TruncMonth
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)

# Bangladesh agricultural calendar — monthly product demand signals
BD_AGRI_CALENDAR = {
    1:  {"season": "Winter (Rabi)", "high_demand": ["wheat seed", "mustard", "potato", "fertilizer"]},
    2:  {"season": "Winter (Rabi)", "high_demand": ["fungicide", "insecticide", "harvest tools"]},
    3:  {"season": "Pre-Kharif",   "high_demand": ["paddy seed", "irrigation equipment", "fertilizer"]},
    4:  {"season": "Kharif starts","high_demand": ["rice seed", "pesticide", "drip irrigation"]},
    5:  {"season": "Kharif",       "high_demand": ["urea", "potash", "fungicide", "spray pump"]},
    6:  {"season": "Monsoon Kharif","high_demand": ["fungicide", "flood-resistant seed", "drainage"]},
    7:  {"season": "Monsoon",      "high_demand": ["blast control", "organic fertilizer"]},
    8:  {"season": "Monsoon",      "high_demand": ["pesticide", "blight control", "soil amendment"]},
    9:  {"season": "Late Kharif",  "high_demand": ["harvest equipment", "post-harvest treatment"]},
    10: {"season": "Rabi prep",    "high_demand": ["vegetable seed", "compost", "npk fertilizer"]},
    11: {"season": "Rabi",         "high_demand": ["wheat seed", "onion seed", "garlic seed", "urea"]},
    12: {"season": "Rabi",         "high_demand": ["potato", "cold-season vegetable", "fungicide"]},
}


class ForecastService:
    """Builds forecast data packages consumed by ForecastAgent."""

    def build_merchant_forecast(self, merchant_account) -> dict:
        """Build a merchant-specific demand forecast from their sales history."""
        try:
            from orders.models import Order, OrderItem
            revenue_expr = ExpressionWrapper(
                F("product_price_snapshot") * F("quantity"), output_field=DecimalField()
            )
            # Last 6 months sales by product
            cutoff = timezone.now() - timedelta(days=180)
            monthly = list(
                OrderItem.objects.filter(
                    order__merchant=merchant_account,
                    order__created_at__gte=cutoff,
                    order__status__in=[Order.STATUS_DELIVERED, Order.STATUS_COMPLETED],
                )
                .annotate(month=TruncMonth("order__created_at"))
                .values("month", "product_name_snapshot")
                .annotate(units=Sum("quantity"), rev=Sum(revenue_expr))
                .order_by("month", "-units")
            )
            for m in monthly:
                m["rev"] = float(m.get("rev") or 0)
                if m.get("month"):
                    m["month"] = m["month"].strftime("%Y-%m")

            # Current month info
            now = timezone.now()
            cal = BD_AGRI_CALENDAR.get(now.month, {})

            return {
                "historical_sales": monthly,
                "current_season":   cal.get("season", ""),
                "seasonal_high_demand": cal.get("high_demand", []),
                "next_month":       (now.replace(day=1) + timedelta(days=32)).strftime("%B"),
                "analysis_period":  "Last 6 months",
            }
        except Exception as exc:
            logger.error("ForecastService.build_merchant_forecast error: %s", exc)
            return {}

    def build_platform_forecast(self) -> dict:
        """Build platform-wide demand forecast (for non-merchant users)."""
        try:
            from orders.models import Order, OrderItem
            revenue_expr = ExpressionWrapper(
                F("product_price_snapshot") * F("quantity"), output_field=DecimalField()
            )
            cutoff = timezone.now() - timedelta(days=90)
            top_products = list(
                OrderItem.objects.filter(
                    order__created_at__gte=cutoff,
                    order__status__in=[Order.STATUS_DELIVERED, Order.STATUS_COMPLETED],
                )
                .values("product_name_snapshot")
                .annotate(total_units=Sum("quantity"), total_rev=Sum(revenue_expr))
                .order_by("-total_units")[:15]
            )
            for p in top_products:
                p["total_rev"] = float(p.get("total_rev") or 0)

            now = timezone.now()
            cal = BD_AGRI_CALENDAR.get(now.month, {})

            return {
                "trending_products": top_products,
                "current_season":    cal.get("season", ""),
                "seasonal_high_demand": cal.get("high_demand", []),
                "next_month":        (now.replace(day=1) + timedelta(days=32)).strftime("%B"),
                "forecast_basis":    "90-day platform sales data + Bangladesh agricultural calendar",
            }
        except Exception as exc:
            logger.error("ForecastService.build_platform_forecast error: %s", exc)
            return {}


forecast_service = ForecastService()
