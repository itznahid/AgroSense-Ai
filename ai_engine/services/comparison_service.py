"""
comparison_service.py — Product Comparison Data Service
Enriches product objects with DB analytics for comparison.
"""
from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


class ComparisonService:
    """Builds enriched product data dicts for the ComparisonAgent."""

    def enrich_product(self, product) -> dict:
        """Return a rich data dict about a product including reviews and sales data."""
        from orders.models import OrderItem
        try:
            # Sales count
            units_sold = sum(
                item.quantity
                for item in OrderItem.objects.filter(product=product)
            )
        except Exception:
            units_sold = 0

        # Reviews
        from ai_engine.services.review_service import review_service
        reviews = review_service.get_reviews_for_product(product.id)
        review_count = len(reviews)
        avg_rating = (
            sum(r.get("rating", 0) for r in reviews) / review_count
            if review_count else float(product.rating)
        )

        return {
            "id": product.pk,
            "name": product.name,
            "price": float(product.price),
            "original_price": float(product.original_price) if product.original_price else None,
            "category": product.category.name,
            "rating": round(avg_rating, 1),
            "review_count": review_count or product.review_count,
            "units_sold": units_sold,
            "stock": product.stock,
            "in_stock": product.in_stock,
            "badge": product.badge,
            "description": product.description[:300],
            "suitable_crops": product.suitable_crops,
            "recent_reviews": reviews[:10],
        }


comparison_service = ComparisonService()
