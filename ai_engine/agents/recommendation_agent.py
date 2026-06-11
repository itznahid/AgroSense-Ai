"""
recommendation_agent.py — Smart Personalized Recommendation Agent
Uses Digital Twin profile + current context for explainable recommendations.
"""
from __future__ import annotations
import json
from ai_engine.agents.orchestrator import AgentResponse
from ai_engine.services.gemini_service import gemini_service
from ai_engine.services.recommendation_service import recommendation_service
from ai_engine.services.prompt_manager import PromptManager


class RecommendationAgent:
    """
    Generates explainable product recommendations powered by Digital Twin data.
    Every recommendation includes: reason, confidence, expected benefit, risk info.
    """

    def handle(self, user, query: str, context: dict = None) -> AgentResponse:
        context = context or {}

        # 1. Get or build digital twin profile
        user_profile = self._get_user_profile(user)

        # 2. Get relevant products from DB
        products = recommendation_service.get_candidates(
            user=user,
            query=query,
            profile=user_profile,
            limit=6,
        )

        if not products:
            return AgentResponse(
                text=(
                    "I don't have enough purchase history or context to make personalized "
                    "recommendations yet. Browse our marketplace to discover products, and your "
                    "recommendations will improve over time!"
                ),
                agent_type="recommendation_agent",
            )

        # 3. Serialize products for AI
        products_text = "\n".join(
            f"ID:{p.pk} | {p.name} | ৳{p.price} | {p.category.name} | "
            f"Rating:{p.rating}★ | {'In Stock' if p.in_stock else 'Out of Stock'}"
            for p in products
        )

        # 4. Build context string
        context_parts = []
        if context.get("disease"):
            context_parts.append(f"Recent disease scan: {context['disease']}")
        if context.get("weather"):
            context_parts.append(f"Weather: {context['weather']}")
        context_parts.append(f"User query: {query}")

        # 5. Get AI-powered ranked recommendations
        prompt = PromptManager.build_recommendation_prompt(
            user_profile=user_profile,
            available_products=products_text,
            context="; ".join(context_parts),
        )
        recs_data = gemini_service.generate_json(
            prompt=prompt,
            system_prompt=PromptManager.RECOMMENDATION_SYSTEM,
            temperature=0.3,
            agent_type="recommendation_agent",
        )

        # 6. Format response
        if recs_data and isinstance(recs_data, dict):
            text = self._format_recommendations(recs_data, user_profile)
        else:
            text = self._fallback_text(products)

        return AgentResponse(
            text=text,
            agent_type="recommendation_agent",
            products=products[:4],
            metadata={"personalized": bool(user_profile.get("total_orders", 0) > 0)},
        )

    @staticmethod
    def _get_user_profile(user) -> dict:
        try:
            from ai_engine.models import DigitalTwin
            twin = DigitalTwin.get_or_create_for_user(user)
            return twin.ai_profile or {}
        except Exception:
            return {}

    @staticmethod
    def _format_recommendations(data: dict, profile: dict) -> str:
        recs = data.get("recommendations", [])
        summary = data.get("personalization_summary", "")
        lines = ["## 🌱 Personalized Recommendations\n"]
        if summary:
            lines.append(f"*{summary}*\n")
        for i, rec in enumerate(recs[:4], 1):
            lines.extend([
                f"### {i}. {rec.get('product_name', 'Product')} "
                f"[{rec.get('priority', 'Medium')} Priority]",
                f"**Why:** {rec.get('reason', '')}",
                f"**Expected benefit:** {rec.get('expected_benefit', '')}",
                f"**Confidence:** {rec.get('confidence_score', 'N/A')}/100",
                f"**Risk info:** {rec.get('risk_info', 'None')}\n",
            ])
        return "\n".join(lines)

    @staticmethod
    def _fallback_text(products) -> str:
        names = ", ".join(p.name for p in products[:3])
        return (
            f"Based on your activity, I recommend: **{names}**. "
            "These are top-rated products in our marketplace. "
            "As you make more purchases, your recommendations will become more personalized."
        )


recommendation_agent = RecommendationAgent()
