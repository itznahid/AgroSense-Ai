"""
product_search_service.py — DB-backed Product Search
All results come from the database. Never hallucinates.
"""
from __future__ import annotations
import logging
from django.db.models import Q

logger = logging.getLogger(__name__)


class ProductSearchService:
    """
    Searches the marketplace Product table using keyword + intent matching.
    Supports price filters extracted from natural language queries.
    """

    # Intent → related keywords
    INTENT_KEYWORDS: dict[str, list[str]] = {
        "fertilizer":  ["fertilizer", "fertiliser", "urea", "npk", "compost", "manure", "nutrient"],
        "pesticide":   ["pesticide", "insecticide", "pest control", "spray", "killer"],
        "fungicide":   ["fungicide", "fungal", "antifungal", "blast", "blight"],
        "herbicide":   ["herbicide", "weedicide", "weed killer", "weed control"],
        "seed":        ["seed", "seedling", "sapling", "variety"],
        "irrigation":  ["irrigation", "drip", "sprinkler", "pipe", "pump", "water"],
        "soil":        ["soil", "compost", "organic", "humus"],
        "tool":        ["tool", "sickle", "spade", "hoe", "machine", "equipment"],
        # ── Food / Produce / Nutrition ─────────────────────────────────────────
        "vegetable":   ["vegetable", "veggie", "greens", "spinach", "bitter gourd", "karela",
                        "brinjal", "eggplant", "tomato", "cucumber", "okra", "pumpkin",
                        "cauliflower", "cabbage", "bean", "pea", "drumstick", "moringa",
                        "শাক", "সবজি", "করলা", "পালং"],
        "fruit":       ["fruit", "banana", "papaya", "mango", "guava", "jackfruit", "lemon",
                        "orange", "watermelon", "pineapple", "coconut", "date", "fig",
                        "ফল", "কলা", "পেঁপে", "আম", "পেয়ারা"],
        "grain_cereal":["rice", "oats", "wheat", "brown rice", "barley", "millet", "maize",
                        "corn", "grain", "cereal", "চাল", "ভুট্টা", "গম"],
        "legume_pulse":["lentil", "dal", "dhal", "chickpea", "soybean", "mung bean", "pea",
                        "kidney bean", "pulse", "legume", "মসুর", "ছোলা", "ডাল", "মটর"],
        "spice_herb":  ["ginger", "garlic", "turmeric", "fenugreek", "cumin", "coriander",
                        "chilli", "pepper", "spice", "herb", "আদা", "রসুন", "হলুদ"],
        "dairy_egg":   ["milk", "egg", "yogurt", "curd", "dairy", "paneer", "cheese",
                        "দুধ", "ডিম", "দই"],
        "organic_food":["organic", "natural food", "healthy food", "fresh produce", "farm fresh",
                        "জৈব", "প্রাকৃতিক"],
    }

    def search(
        self,
        query: str,
        limit: int = 6,
        user=None,
        min_price: float = None,
        max_price: float = None,
        category: str = None,
        crop: str = None,
    ) -> list:
        """
        Search products matching the query. Returns a list of Product ORM objects.
        """
        from marketplace.models import Product

        try:
            qs = Product.objects.filter(is_active=True).select_related(
                "category", "merchant__merchant_profile"
            )

            # Price filter extraction from query
            if max_price is None:
                max_price = self._extract_price_limit(query)

            if max_price:
                qs = qs.filter(price__lte=max_price)
            if min_price:
                qs = qs.filter(price__gte=min_price)

            # Category filter
            if category:
                qs = qs.filter(category__name__icontains=category)

            # Build search Q
            q = Q()

            # Detect intent and expand keywords
            for intent, keywords in self.INTENT_KEYWORDS.items():
                if any(kw in query.lower() for kw in keywords):
                    for kw in keywords[:3]:
                        q |= Q(name__icontains=kw) | Q(description__icontains=kw)

            # Crop-specific search
            if crop:
                q |= (
                    Q(name__icontains=crop)
                    | Q(description__icontains=crop)
                    | Q(suitable_crops__icontains=crop)
                )

            # Generic keyword search (words > 3 chars)
            stop_words = {
                "show", "find", "give", "what", "best", "under", "above",
                "with", "from", "that", "this", "have", "does", "want",
            }
            for word in query.lower().split():
                if len(word) > 3 and word not in stop_words:
                    q |= (
                        Q(name__icontains=word)
                        | Q(description__icontains=word)
                        | Q(suitable_crops__icontains=word)
                    )

            if q:
                qs = qs.filter(q)

            return list(qs.order_by("-rating", "-review_count")[:limit])

        except Exception as exc:
            logger.error("ProductSearchService.search error: %s", exc)
            return []

    def get_by_ids(self, product_ids: list[int]) -> list:
        """Fetch products by ID list (preserving order)."""
        from marketplace.models import Product
        try:
            products = {
                p.id: p
                for p in Product.objects.filter(id__in=product_ids, is_active=True)
                .select_related("category", "merchant__merchant_profile")
            }
            return [products[pid] for pid in product_ids if pid in products]
        except Exception as exc:
            logger.error("ProductSearchService.get_by_ids error: %s", exc)
            return []

    def get_top_products(self, limit: int = 4) -> list:
        """Return top-rated active products as fallback."""
        from marketplace.models import Product
        try:
            return list(
                Product.objects.filter(is_active=True)
                .select_related("category", "merchant__merchant_profile")
                .order_by("-rating", "-review_count")[:limit]
            )
        except Exception:
            return []

    @staticmethod
    def _extract_price_limit(query: str) -> float | None:
        """Extract a BDT price ceiling from natural language (e.g. 'under 500 BDT')."""
        import re
        patterns = [
            r"under\s+(?:tk\.?|taka|bdt)?\s*(\d+)",
            r"below\s+(?:tk\.?|taka|bdt)?\s*(\d+)",
            r"less\s+than\s+(?:tk\.?|taka|bdt)?\s*(\d+)",
            r"(?:tk\.?|taka|bdt)\s*(\d+)\s*(?:or\s+)?(?:less|below|under)",
            r"(\d+)\s*(?:tk\.?|taka|bdt)\s*(?:or\s+)?(?:less|below|under)",
            r"max\w*\s+(?:tk\.?|taka|bdt)?\s*(\d+)",
            r"(\d+)\s+(?:tk\.?|taka|bdt)",
        ]
        for pattern in patterns:
            m = re.search(pattern, query.lower())
            if m:
                return float(m.group(1))
        return None

    def serialize(self, product) -> dict:
        """Serialize a Product ORM object to a JSON-safe dict for API/AI use."""
        img = product.image.url if product.image else None
        try:
            merchant_name = product.merchant.merchant_profile.shop_name
        except Exception:
            merchant_name = "AgroSense Store"
        return {
            "id":           product.pk,
            "name":         product.name,
            "price":        float(product.price),
            "original_price": float(product.original_price) if product.original_price else None,
            "unit":         product.unit,
            "category":     product.category.name,
            "merchant":     merchant_name,
            "rating":       float(product.rating),
            "review_count": product.review_count,
            "in_stock":     product.in_stock,
            "stock":        product.stock,
            "icon":         product.icon,
            "image":        img,
            "badge":        product.badge,
            "suitable_crops": product.suitable_crops,
        }


product_search_service = ProductSearchService()
