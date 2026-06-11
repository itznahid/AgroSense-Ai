"""
ai_engine/models.py
===================
Enterprise models:
  • AIKeyConfig    — DB-managed Gemini API keys (admin-editable, no code deploy needed)
  • AICallLog      — Every Gemini call logged for monitoring dashboard
  • DigitalTwin    — Per-user AI behavioral profile (continuously learning)
  • MerchantTwin   — Per-merchant AI business profile (continuously learning)
"""
from __future__ import annotations

import logging

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)


# ── Gemini Key Management ──────────────────────────────────────────────────────

class AIKeyConfig(models.Model):
    """
    DB-managed Gemini API key.
    Admins can add, remove, enable, disable, and reorder keys through the UI
    without any code changes or deployment.
    """
    PRIORITY_PRIMARY   = 1
    PRIORITY_SECONDARY = 2
    PRIORITY_EMERGENCY = 3

    name        = models.CharField(max_length=100, help_text="E.g. 'Primary Key', 'Backup Key 1'")
    api_key     = models.CharField(
        max_length=500,
        help_text="Gemini API key from Google AI Studio",
    )
    priority    = models.PositiveSmallIntegerField(
        default=PRIORITY_SECONDARY,
        help_text="Lower number = higher priority. 1=Primary, 2=Secondary, 3=Emergency",
    )
    is_active   = models.BooleanField(default=True, help_text="Uncheck to disable without deleting")
    notes       = models.TextField(blank=True, help_text="Optional notes (e.g. quota limit, project)")
    created_at  = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering   = ["priority", "name"]
        verbose_name       = "Gemini API Key"
        verbose_name_plural = "Gemini API Keys"

    def __str__(self):
        status = "✅" if self.is_active else "❌"
        return f"{status} [{self.priority}] {self.name}"

    def masked_key(self) -> str:
        """Return a safely masked version of the API key for display."""
        if len(self.api_key) < 8:
            return "***"
        return self.api_key[:6] + "..." + self.api_key[-4:]

    def success_rate(self) -> float:
        """Compute success rate from call logs."""
        total = AICallLog.objects.filter(db_key_id=self.id).count()
        if not total:
            return 0.0
        success = AICallLog.objects.filter(db_key_id=self.id, success=True).count()
        return round(success / total * 100, 1)


# ── API Call Log (Monitoring) ──────────────────────────────────────────────────

class AICallLog(models.Model):
    """
    Logs every Gemini API call for the admin monitoring dashboard.
    High-write table — no FKs to avoid lock contention.
    """
    key_index   = models.PositiveSmallIntegerField(help_text="0=primary, 1=secondary, 2=emergency")
    db_key_id   = models.IntegerField(null=True, blank=True, help_text="AIKeyConfig.id if DB-managed")
    model_used  = models.CharField(max_length=60)
    success     = models.BooleanField()
    error_type  = models.CharField(max_length=200, blank=True)
    latency_ms  = models.PositiveIntegerField(default=0)
    agent_type  = models.CharField(max_length=80, blank=True)
    is_failover = models.BooleanField(default=False, help_text="True when a backup key/model was used")
    timestamp   = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name       = "AI Call Log"
        verbose_name_plural = "AI Call Logs"

    def __str__(self):
        status = "✅" if self.success else "❌"
        return f"{status} {self.model_used} [{self.agent_type}] {self.latency_ms}ms"


# ── Customer Digital Twin ──────────────────────────────────────────────────────

class DigitalTwin(models.Model):
    """
    Per-user AI behavioral profile — continuously learns from interactions.

    The twin aggregates:
      • Purchase history (orders, order items)
      • Disease scan history
      • Wishlist behavior
      • Chat interactions
      • Search patterns

    Call rebuild() to recompute from live DB data.
    The ai_profile JSON is used by RecommendationAgent for personalization.
    """
    user              = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="digital_twin"
    )
    ai_profile        = models.JSONField(
        default=dict,
        help_text="Computed behavioral profile used by AI agents",
    )
    crops_grown       = models.JSONField(default=list)
    preferred_categories = models.JSONField(default=list)
    budget_range      = models.CharField(max_length=20, blank=True, default="medium")
    brand_preferences = models.JSONField(default=list)
    disease_history   = models.JSONField(default=list)
    total_orders      = models.PositiveIntegerField(default=0)
    total_spent_bdt   = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    avg_order_value   = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    purchase_frequency = models.CharField(max_length=20, blank=True, default="monthly")
    last_updated      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name       = "Customer Digital Twin"
        verbose_name_plural = "Customer Digital Twins"

    def __str__(self):
        return f"DigitalTwin({self.user.username})"

    def rebuild(self) -> None:
        """Recompute the behavioral profile from live DB data."""
        try:
            raw = self._collect_raw_data()
            self.crops_grown          = raw.get("crops_grown", [])
            self.preferred_categories = raw.get("preferred_categories", [])
            self.disease_history      = raw.get("disease_history", [])
            self.total_orders         = raw.get("total_orders", 0)
            self.total_spent_bdt      = raw.get("total_spent", 0)
            self.avg_order_value      = raw.get("avg_order_value", 0)
            self.budget_range         = self._infer_budget(raw.get("avg_order_value", 0))
            self.purchase_frequency   = raw.get("purchase_frequency", "monthly")
            # Store full raw data as AI profile for agent consumption
            self.ai_profile = raw
            self.save()
        except Exception as exc:
            logger.error("DigitalTwin.rebuild failed for user %s: %s", self.user_id, exc)

    def _collect_raw_data(self) -> dict:
        """Query DB for all behavioral signals."""
        from orders.models import Order, OrderItem
        from marketplace.models import WishlistItem
        from django.db.models import Sum, Count

        user = self.user

        # Orders
        orders = Order.objects.filter(customer=user)
        total_orders = orders.count()
        total_spent = float(orders.aggregate(s=Sum("total_amount"))["s"] or 0)
        avg_order = round(total_spent / total_orders, 2) if total_orders else 0

        # Category preferences from order items
        items = OrderItem.objects.filter(order__customer=user).select_related("product__category")
        cat_counts: dict[str, int] = {}
        for item in items:
            if item.product and item.product.category:
                cat = item.product.category.name
                cat_counts[cat] = cat_counts.get(cat, 0) + item.quantity
        preferred_cats = sorted(cat_counts, key=cat_counts.get, reverse=True)[:5]

        # Disease scans
        try:
            from crop_disease.models import CropDiseaseScan
            scans = CropDiseaseScan.objects.filter(user=user)
            crops = list({s.crop_name for s in scans if s.crop_name})
            diseases = list({s.predicted_class for s in scans if s.predicted_class and not s.is_healthy})
        except Exception:
            crops, diseases = [], []

        # Wishlist
        try:
            wishlist_items = WishlistItem.objects.filter(
                wishlist__user=user
            ).select_related("product__category")
            wishlist_cats = list({i.product.category.name for i in wishlist_items if i.product and i.product.category})
        except Exception:
            wishlist_cats = []

        # Purchase frequency (rough heuristic)
        if total_orders == 0:
            frequency = "new_user"
        elif total_orders >= 12:
            frequency = "monthly"
        elif total_orders >= 4:
            frequency = "quarterly"
        else:
            frequency = "occasional"

        # Recent products (last 10 order items)
        recent_products = list(
            OrderItem.objects.filter(order__customer=user)
            .select_related("product__category")
            .order_by("-order__created_at")
            .values("product_name_snapshot", "product_price_snapshot")[:10]
        )

        return {
            "total_orders": total_orders,
            "total_spent": total_spent,
            "avg_order_value": avg_order,
            "preferred_categories": preferred_cats,
            "crops_grown": crops,
            "disease_history": diseases,
            "wishlist_categories": wishlist_cats,
            "purchase_frequency": frequency,
            "recent_products": recent_products,
            "budget_range": self._infer_budget(avg_order),
        }

    @staticmethod
    def _infer_budget(avg_order_value: float) -> str:
        if avg_order_value == 0:
            return "unknown"
        if avg_order_value < 500:
            return "low"
        if avg_order_value < 2000:
            return "medium"
        return "high"

    @classmethod
    def get_or_create_for_user(cls, user: User) -> "DigitalTwin":
        twin, created = cls.objects.get_or_create(user=user)
        # Auto-rebuild if first time or older than 24 hours
        if created or (timezone.now() - twin.last_updated).seconds > 86400:
            twin.rebuild()
        return twin


# ── Merchant Digital Twin ──────────────────────────────────────────────────────

class MerchantTwin(models.Model):
    """
    Per-merchant AI business intelligence profile.

    Learns from:
      • Sales data (OrderItems)
      • Product performance
      • Revenue trends
      • Customer segments
      • Inventory levels
    """
    merchant          = models.OneToOneField(
        "accounts.UserAccount",
        on_delete=models.CASCADE,
        related_name="merchant_twin",
    )
    analytics_cache   = models.JSONField(
        default=dict,
        help_text="Cached analytics used by MerchantAgent",
    )
    top_products      = models.JSONField(default=list)
    revenue_trend     = models.JSONField(default=dict)
    customer_segments = models.JSONField(default=dict)
    seasonal_patterns = models.JSONField(default=dict)
    total_revenue     = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    total_orders_served = models.PositiveIntegerField(default=0)
    last_updated      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name       = "Merchant Digital Twin"
        verbose_name_plural = "Merchant Digital Twins"

    def __str__(self):
        return f"MerchantTwin({self.merchant})"

    def rebuild(self) -> None:
        """Recompute merchant business intelligence from live data."""
        try:
            data = self._collect_merchant_data()
            self.top_products      = data.get("top_products", [])
            self.revenue_trend     = data.get("revenue_trend", {})
            self.customer_segments = data.get("customer_segments", {})
            self.seasonal_patterns = data.get("seasonal_patterns", {})
            self.total_revenue     = data.get("total_revenue", 0)
            self.total_orders_served = data.get("total_orders", 0)
            self.analytics_cache   = data
            self.save()
        except Exception as exc:
            logger.error("MerchantTwin.rebuild failed for merchant %s: %s", self.merchant_id, exc)

    def _collect_merchant_data(self) -> dict:
        """Gather all merchant-specific data."""
        from orders.models import OrderItem, Order
        from marketplace.models import Product
        from django.db.models import Sum, Count, F, ExpressionWrapper, DecimalField
        from django.db.models.functions import TruncMonth

        merchant = self.merchant

        # All order items for this merchant
        items = OrderItem.objects.filter(order__merchant=merchant)

        # Total revenue from delivered orders
        total_rev = float(
            items.filter(order__status__in=[Order.STATUS_DELIVERED, Order.STATUS_COMPLETED])
            .aggregate(
                rev=Sum(
                    ExpressionWrapper(
                        F("product_price_snapshot") * F("quantity"),
                        output_field=DecimalField()
                    )
                )
            )["rev"] or 0
        )

        # Top products by units sold
        top_prods = list(
            items.values("product_name_snapshot")
            .annotate(
                units_sold=Sum("quantity"),
                revenue=Sum(
                    ExpressionWrapper(
                        F("product_price_snapshot") * F("quantity"),
                        output_field=DecimalField()
                    )
                ),
            )
            .order_by("-units_sold")[:10]
        )
        # Convert Decimal to float for JSON serialization
        for p in top_prods:
            p["revenue"] = float(p.get("revenue") or 0)

        # Monthly revenue trend (last 6 months)
        monthly = list(
            items.filter(order__status__in=[Order.STATUS_DELIVERED, Order.STATUS_COMPLETED])
            .annotate(month=TruncMonth("order__created_at"))
            .values("month")
            .annotate(
                revenue=Sum(
                    ExpressionWrapper(
                        F("product_price_snapshot") * F("quantity"),
                        output_field=DecimalField()
                    )
                ),
                orders=Count("order", distinct=True),
            )
            .order_by("-month")[:6]
        )
        revenue_trend = {
            str(r["month"].strftime("%Y-%m") if r["month"] else ""): {
                "revenue": float(r.get("revenue") or 0),
                "orders": r.get("orders", 0),
            }
            for r in monthly
        }

        # Current inventory
        products = list(
            Product.objects.filter(merchant=merchant, is_active=True)
            .values("name", "stock", "price", "rating", "review_count")
        )
        for p in products:
            p["price"] = float(p.get("price") or 0)
            p["rating"] = float(p.get("rating") or 0)

        # Total orders served
        total_orders = items.values("order").distinct().count()

        # Repeat customers
        repeat = (
            items.values("order__customer")
            .annotate(order_count=Count("order", distinct=True))
            .filter(order_count__gt=1)
            .count()
        )
        unique_customers = items.values("order__customer").distinct().count()

        return {
            "total_revenue": total_rev,
            "total_orders": total_orders,
            "top_products": top_prods,
            "revenue_trend": revenue_trend,
            "current_inventory": products,
            "unique_customers": unique_customers,
            "repeat_customers": repeat,
            "retention_rate": round(repeat / unique_customers * 100, 1) if unique_customers else 0,
            "customer_segments": {
                "unique": unique_customers,
                "repeat": repeat,
                "new": unique_customers - repeat,
            },
        }

    @classmethod
    def get_or_create_for_merchant(cls, merchant_account) -> "MerchantTwin":
        twin, created = cls.objects.get_or_create(merchant=merchant_account)
        if created or (timezone.now() - twin.last_updated).seconds > 3600:
            twin.rebuild()
        return twin
