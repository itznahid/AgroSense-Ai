"""
review_service.py — Review Data Service
Retrieves and normalizes product reviews from all available sources.
"""
from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


class ReviewService:
    """Aggregates review data for products (from ProductReview model)."""

    def get_reviews_for_product(self, product_id: int, limit: int = 200) -> list[dict]:
        """Return a list of review dicts for a given product ID."""
        try:
            from marketplace.models import ProductReview
            reviews = (
                ProductReview.objects.filter(product_id=product_id)
                .select_related("user")
                .order_by("-created_at")[:limit]
            )
            return [
                {
                    "id":        r.id,
                    "rating":    r.rating,
                    "comment":   r.comment,
                    "user":      r.user.get_full_name() or r.user.username,
                    "verified":  r.is_verified_purchase,
                    "helpful":   r.helpful_votes,
                    "created":   r.created_at.strftime("%Y-%m-%d"),
                    "sentiment": r.sentiment,
                }
                for r in reviews
            ]
        except Exception as exc:
            logger.error("ReviewService.get_reviews_for_product(%s) error: %s", product_id, exc)
            return []

    def get_platform_reviews(
        self,
        product_ids: list[int] = None,
        category: str = None,
        limit: int = 500,
    ) -> list[dict]:
        """Return reviews across multiple products (for platform-wide analysis)."""
        try:
            from marketplace.models import ProductReview
            qs = ProductReview.objects.select_related("product", "user").order_by("-created_at")
            if product_ids:
                qs = qs.filter(product_id__in=product_ids)
            if category:
                qs = qs.filter(product__category__name__icontains=category)
            reviews = qs[:limit]
            return [
                {
                    "product":  r.product.name,
                    "rating":   r.rating,
                    "comment":  r.comment,
                    "verified": r.is_verified_purchase,
                }
                for r in reviews
            ]
        except Exception as exc:
            logger.error("ReviewService.get_platform_reviews error: %s", exc)
            return []

    def add_review(
        self,
        product_id: int,
        user,
        rating: int,
        comment: str,
        is_verified: bool = False,
    ) -> bool:
        """Add a new review. Returns True on success."""
        try:
            from marketplace.models import ProductReview, Product
            product = Product.objects.filter(id=product_id, is_active=True).first()
            if product is None:
                return False
            review, created = ProductReview.objects.get_or_create(
                product=product,
                user=user,
                defaults={
                    "rating":               rating,
                    "comment":              comment,
                    "is_verified_purchase": is_verified,
                },
            )
            if not created:
                # Update existing review
                review.rating  = rating
                review.comment = comment
                review.save(update_fields=["rating", "comment"])

            # Recalculate product average rating
            self._update_product_rating(product)
            return True
        except Exception as exc:
            logger.error("ReviewService.add_review error: %s", exc)
            return False

    @staticmethod
    def _update_product_rating(product) -> None:
        """Recompute the product's aggregate rating from all reviews."""
        try:
            from marketplace.models import ProductReview
            from django.db.models import Avg, Count
            agg = ProductReview.objects.filter(product=product).aggregate(
                avg=Avg("rating"), cnt=Count("id")
            )
            product.rating       = round(agg["avg"] or 0, 2)
            product.review_count = agg["cnt"] or 0
            product.save(update_fields=["rating", "review_count"])
        except Exception:
            pass


review_service = ReviewService()
