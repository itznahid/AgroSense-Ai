"""
analytics_service.py — Merchant Analytics Data Service
Builds comprehensive analytics reports for authenticated merchants.
All queries are scoped strictly to merchant-owned data.
"""
from __future__ import annotations
import logging
from django.db.models import Sum, Count, Avg, F, ExpressionWrapper, DecimalField
from django.db.models.functions import TruncMonth, TruncWeek
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Strict merchant-scoped analytics builder. No cross-merchant data leakage."""

    def build_analytics(self, merchant_account) -> dict:
        """Build complete analytics report for a merchant."""
        try:
            from orders.models import OrderItem, Order
            from marketplace.models import Product
        except ImportError as exc:
            logger.error("Analytics import error: %s", exc)
            return {}

        items = OrderItem.objects.filter(order__merchant=merchant_account)
        delivered = items.filter(order__status__in=[Order.STATUS_DELIVERED, Order.STATUS_COMPLETED])
        now = timezone.now()

        revenue_expr = ExpressionWrapper(
            F("product_price_snapshot") * F("quantity"), output_field=DecimalField()
        )

        # ── Revenue totals ────────────────────────────────────────────────────
        total_rev   = float(delivered.aggregate(r=Sum(revenue_expr))["r"] or 0)
        this_month  = delivered.filter(order__created_at__month=now.month, order__created_at__year=now.year)
        month_rev   = float(this_month.aggregate(r=Sum(revenue_expr))["r"] or 0)
        last_month_start = (now.replace(day=1) - timedelta(days=1)).replace(day=1)
        last_month  = delivered.filter(
            order__created_at__gte=last_month_start,
            order__created_at__lt=now.replace(day=1),
        )
        prev_rev    = float(last_month.aggregate(r=Sum(revenue_expr))["r"] or 0)
        growth_pct  = round((month_rev - prev_rev) / prev_rev * 100, 1) if prev_rev else 0

        # ── Orders ────────────────────────────────────────────────────────────
        total_orders = items.values("order").distinct().count()
        this_week    = items.filter(order__created_at__gte=now - timedelta(days=7))
        week_orders  = this_week.values("order").distinct().count()

        # ── Top products ──────────────────────────────────────────────────────
        top_products = list(
            delivered.values("product_name_snapshot", "product_id")
            .annotate(units=Sum("quantity"), rev=Sum(revenue_expr))
            .order_by("-units")[:10]
        )
        for p in top_products:
            p["rev"] = float(p.get("rev") or 0)

        # ── Monthly trend (last 6 months) ─────────────────────────────────────
        monthly = list(
            delivered
            .annotate(month=TruncMonth("order__created_at"))
            .values("month")
            .annotate(revenue=Sum(revenue_expr), orders=Count("order", distinct=True))
            .order_by("-month")[:6]
        )
        monthly_trend = [
            {
                "month":   m["month"].strftime("%b %Y") if m["month"] else "",
                "revenue": float(m.get("revenue") or 0),
                "orders":  m.get("orders", 0),
            }
            for m in monthly
        ]

        # ── Customers ─────────────────────────────────────────────────────────
        unique_customers = items.values("order__customer").distinct().count()
        repeat_customers = (
            items.values("order__customer")
            .annotate(cnt=Count("order", distinct=True))
            .filter(cnt__gt=1)
            .count()
        )
        retention = round(repeat_customers / unique_customers * 100, 1) if unique_customers else 0

        # ── Inventory ─────────────────────────────────────────────────────────
        inventory = list(
            Product.objects.filter(merchant=merchant_account, is_active=True)
            .values("name", "stock", "price", "rating")
            .order_by("stock")[:20]
        )
        for p in inventory:
            p["price"] = float(p.get("price") or 0)

        low_stock = [p for p in inventory if p["stock"] < 10]

        # ── Average order value ───────────────────────────────────────────────
        aov = round(total_rev / total_orders, 2) if total_orders else 0

        return {
            "total_revenue_bdt":   total_rev,
            "monthly_revenue_bdt": month_rev,
            "revenue_growth_pct":  growth_pct,
            "total_orders":        total_orders,
            "weekly_orders":       week_orders,
            "avg_order_value_bdt": aov,
            "unique_customers":    unique_customers,
            "repeat_customers":    repeat_customers,
            "retention_rate_pct":  retention,
            "top_products":        top_products,
            "monthly_trend":       monthly_trend,
            "inventory_snapshot":  inventory,
            "low_stock_alerts":    low_stock,
            "generated_at":        now.strftime("%Y-%m-%d %H:%M"),
        }


analytics_service = AnalyticsService()
