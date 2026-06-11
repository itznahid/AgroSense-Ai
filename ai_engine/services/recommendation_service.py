"""
recommendation_service.py — Smart Recommendation Candidate Builder
Assembles product candidate pools using Digital Twin profile + context.
"""
from __future__ import annotations
import logging
from django.db.models import Q

logger = logging.getLogger(__name__)


class RecommendationService:
    """
    Builds a pool of candidate products for the RecommendationAgent to rank.
    Pulls from: purchase history, wishlist, disease history, seasonal patterns.
    """

    def get_candidates(
        self,
        user,
        query: str = "",
        profile: dict = None,
        limit: int = 6,
    ) -> list:
        """Return candidate Product objects for AI ranking."""
        from marketplace.models import Product

        profile = profile or {}
        qs = Product.objects.filter(is_active=True).select_related(
            "category", "merchant__merchant_profile"
        )

        filters = Q()

        # From preferred categories
        for cat in profile.get("preferred_categories", [])[:3]:
            filters |= Q(category__name__icontains=cat)

        # From crops grown (match to suitable_crops field)
        for crop in profile.get("crops_grown", [])[:3]:
            filters |= Q(suitable_crops__icontains=crop)

        # From disease history (match treatment products)
        for disease in profile.get("disease_history", [])[:2]:
            disease_keywords = self._disease_to_keywords(disease)
            for kw in disease_keywords:
                filters |= Q(name__icontains=kw) | Q(description__icontains=kw)

        # From wishlist categories
        for cat in profile.get("wishlist_categories", [])[:2]:
            filters |= Q(category__name__icontains=cat)

        # From query keywords
        stop_words = {
            "what", "should", "which", "best", "good", "buy", "recommend",
            "suggest", "show", "give", "tell", "help", "about", "product",
        }
        for word in query.lower().split():
            if len(word) > 3 and word not in stop_words:
                filters |= Q(name__icontains=word) | Q(description__icontains=word)

        if filters:
            qs = qs.filter(filters)

        # Budget filter
        budget_range = profile.get("budget_range", "")
        if budget_range == "low":
            qs = qs.filter(price__lte=500)
        elif budget_range == "medium":
            qs = qs.filter(price__lte=2000)

        # Exclude recently purchased products (last 30 days)
        excluded_ids = self._get_recent_purchase_ids(user, days=30)
        if excluded_ids:
            qs = qs.exclude(id__in=excluded_ids)

        candidates = list(qs.order_by("-rating", "-review_count")[:limit])

        # If not enough, fill with top-rated products
        if len(candidates) < limit:
            top = list(
                Product.objects.filter(is_active=True)
                .exclude(id__in=[p.id for p in candidates])
                .select_related("category", "merchant__merchant_profile")
                .order_by("-rating")[:limit - len(candidates)]
            )
            candidates.extend(top)

        return candidates[:limit]

    @staticmethod
    def _disease_to_keywords(disease_name: str) -> list[str]:
        """Map disease names to relevant product keyword hints."""
        mapping = {
            "blast":         ["tricyclazole", "fungicide", "blast"],
            "blight":        ["mancozeb", "fungicide", "copper"],
            "rust":          ["propiconazole", "fungicide"],
            "wilt":          ["carbendazim", "soil treatment"],
            "rot":           ["fungicide", "organic treatment"],
            "mosaic":        ["insecticide", "aphid control"],
            "aphid":         ["insecticide", "neem"],
            "whitefly":      ["insecticide", "spray"],
            "leaf curl":     ["insecticide", "virus control"],
            "leaf spot":     ["fungicide", "copper"],
        }
        name_lower = disease_name.lower()
        for key, kws in mapping.items():
            if key in name_lower:
                return kws
        return [disease_name.split()[0]] if disease_name else []

    @staticmethod
    def _get_recent_purchase_ids(user, days: int = 30) -> list[int]:
        """Return product IDs purchased by user in the last N days."""
        from django.utils import timezone
        from datetime import timedelta
        try:
            from orders.models import OrderItem
            cutoff = timezone.now() - timedelta(days=days)
            items = OrderItem.objects.filter(
                order__customer=user,
                order__created_at__gte=cutoff,
            ).values_list("product_id", flat=True)
            return list(set(filter(None, items)))
        except Exception:
            return []


recommendation_service = RecommendationService()
