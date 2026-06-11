"""
disease_detector.py — Gemini Vision Disease Detector + Commerce Integration
============================================================================
Analyzes crop images, identifies diseases, and links to marketplace treatment products.
"""
from __future__ import annotations
import json
import logging
import re

from ai_engine.services.gemini_service import gemini_service
from ai_engine.services.prompt_manager import PromptManager

logger = logging.getLogger(__name__)


class NotAPlantImageError(Exception):
    """Raised when the uploaded image is not a plant/crop image."""


class DiseaseDetectionError(Exception):
    """Raised when disease detection fails after all retries."""


class DiseaseDetector:
    """
    Uses GeminiService (with full multi-key failover) to analyze crop images.
    After detection, automatically queries the marketplace for treatment products.
    """

    def analyze(
        self,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
        user=None,
    ) -> dict:
        """
        Analyze a crop/plant image.

        Returns a result dict with disease info + recommended_products filled
        from the marketplace database.

        Raises:
          NotAPlantImageError  — if not a plant image
          DiseaseDetectionError — if analysis fails
        """
        prompt = PromptManager.DISEASE_ANALYSIS_PROMPT
        raw_text = gemini_service.analyze_image(
            image_bytes=image_bytes,
            prompt=prompt,
            mime_type=mime_type,
            agent_type="disease_vision",
        )

        if not raw_text:
            raise DiseaseDetectionError("No response from AI service. Please try again.")

        result = self._parse_result(raw_text)

        # Check if not a plant image
        if result.get("error") == "NOT_A_PLANT":
            raise NotAPlantImageError(
                result.get("message", "Please upload a clear crop/plant image.")
            )

        if not result or "disease" not in result:
            raise DiseaseDetectionError(
                "Unable to analyze the image. Please upload a clearer photo of the plant."
            )

        # ── Commerce Integration ─────────────────────────────────────────────
        # Fetch treatment products from marketplace and add AI ranking narrative
        result["marketplace_products"] = self._get_treatment_products(result, user)
        result["product_narrative"]    = self._get_product_narrative(result)

        return result

    @staticmethod
    def _parse_result(raw_text: str) -> dict:
        """Parse JSON from Gemini response, stripping markdown code fences."""
        cleaned = re.sub(r"^```(?:json)?\s*", "", raw_text.strip())
        cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            logger.error("Disease detection JSON parse failed: %.400s", raw_text)
            return {}

    @staticmethod
    def _get_treatment_products(result: dict, user=None) -> list:
        """
        Search marketplace for products relevant to the detected disease/crop.
        Returns serialized product dicts.
        """
        from ai_engine.services.product_search_service import product_search_service

        disease  = result.get("disease", "")
        crop     = result.get("crop", "")
        rec_types = result.get("recommended_products", [])

        # Build search queries: disease-specific first, then recommended product types
        search_queries = []
        if disease and disease.lower() != "healthy":
            search_queries.append(f"{disease} treatment {crop}")
        for pt in rec_types[:2]:
            search_queries.append(pt)
        if crop:
            search_queries.append(f"fungicide insecticide {crop}")

        seen_ids: set[int] = set()
        products = []
        for q in search_queries:
            for p in product_search_service.search(query=q, limit=3, user=user):
                if p.pk not in seen_ids:
                    seen_ids.add(p.pk)
                    products.append(product_search_service.serialize(p))
            if len(products) >= 5:
                break

        return products[:5]

    @staticmethod
    def _get_product_narrative(result: dict) -> str:
        """
        Generate a short AI narrative explaining why the marketplace products
        were recommended for the detected disease.
        """
        products = result.get("marketplace_products", [])
        if not products:
            return ""

        from ai_engine.services.prompt_manager import PromptManager
        prompt = PromptManager.build_disease_commerce_prompt(result, products)
        narrative = gemini_service.generate(
            prompt=prompt,
            temperature=0.4,
            agent_type="disease_commerce",
        )
        return narrative or ""


disease_detector = DiseaseDetector()
