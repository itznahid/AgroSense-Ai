"""
marketplace_agent.py — Product Search Agent
Only presents real products from the database. Never hallucinates.
"""
from __future__ import annotations
import json
from ai_engine.agents.orchestrator import AgentResponse
from ai_engine.services.gemini_service import gemini_service
from ai_engine.services.product_search_service import product_search_service
from ai_engine.services.prompt_manager import PromptManager


class MarketplaceAgent:
    """
    Searches the marketplace database and presents results using Gemini
    to generate a natural language summary alongside product cards.
    """

    def handle(self, user, query: str, context: dict = None) -> AgentResponse:
        # 1. Search real DB products
        products = product_search_service.search(query=query, limit=6, user=user)

        if not products:
            return AgentResponse(
                text=(
                    "I searched our marketplace but couldn't find any products matching your query. "
                    "Try different keywords or browse the full marketplace for all available products."
                ),
                agent_type="marketplace_agent",
                products=[],
                metadata={"search_query": query, "result_count": 0},
            )

        # 2. Serialize products for AI context
        products_json = json.dumps(
            [self._serialize(p) for p in products], indent=2, ensure_ascii=False
        )

        # 3. Let Gemini narrate the results (no hallucination possible — DB data only)
        prompt = PromptManager.build_product_search_prompt(query, products_json)
        text = gemini_service.generate(
            prompt=prompt,
            system_prompt=PromptManager.PRODUCT_SEARCH_SYSTEM,
            temperature=0.3,
            agent_type="marketplace_agent",
        )

        if not text:
            text = f"Found {len(products)} products matching your search. See the product cards below."

        return AgentResponse(
            text=text,
            agent_type="marketplace_agent",
            products=products,
            metadata={"search_query": query, "result_count": len(products)},
        )

    @staticmethod
    def _serialize(product) -> dict:
        return {
            "id": product.pk,
            "name": product.name,
            "price_bdt": float(product.price),
            "category": product.category.name,
            "merchant": product.merchant.merchant_profile.shop_name
            if product.merchant and hasattr(product.merchant, "merchant_profile") else "AgroSense",
            "rating": float(product.rating),
            "review_count": product.review_count,
            "in_stock": product.in_stock,
            "stock": product.stock,
            "badge": product.badge,
            "unit": product.unit,
        }


marketplace_agent = MarketplaceAgent()
