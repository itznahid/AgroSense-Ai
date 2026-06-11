"""
review_agent.py — Review Intelligence Agent
Analyzes customer reviews and generates actionable insights.
"""
from __future__ import annotations
import json
from ai_engine.agents.orchestrator import AgentResponse
from ai_engine.services.gemini_service import gemini_service
from ai_engine.services.review_service import review_service
from ai_engine.services.product_search_service import product_search_service
from ai_engine.services.prompt_manager import PromptManager


class ReviewAgent:
    """Summarizes and analyzes product reviews with sentiment intelligence."""

    def handle(self, user, query: str, context: dict = None) -> AgentResponse:
        # Find the product being asked about
        products = product_search_service.search(query=query, limit=1, user=user)
        if not products:
            return AgentResponse(
                text="I couldn't find a product matching your query. Please specify the product name.",
                agent_type="review_agent",
            )

        product = products[0]
        reviews = review_service.get_reviews_for_product(product.id)

        if not reviews:
            return AgentResponse(
                text=(
                    f"**{product.name}** currently has no customer reviews yet.\n\n"
                    f"Overall rating: {product.rating}★ based on {product.review_count} ratings.\n"
                    "Be the first to purchase and review this product!"
                ),
                agent_type="review_agent",
                products=[product],
            )

        # Build review analysis
        prompt = PromptManager.build_review_analysis_prompt(product.name, reviews)
        analysis = gemini_service.generate_json(
            prompt=prompt,
            system_prompt=PromptManager.REVIEW_SYSTEM,
            temperature=0.2,
            agent_type="review_agent",
        )

        if analysis and isinstance(analysis, dict):
            text = self._format_analysis(product.name, analysis)
            metadata = analysis
        else:
            text = f"**{product.name}** has {product.review_count} reviews with an average rating of {product.rating}★."
            metadata = {}

        return AgentResponse(
            text=text,
            agent_type="review_agent",
            products=[product],
            metadata=metadata,
        )

    @staticmethod
    def _format_analysis(product_name: str, a: dict) -> str:
        lines = [
            f"## 📊 Review Analysis: {product_name}\n",
            f"**Overall:** {a.get('average_rating', 'N/A')}★ | "
            f"**Satisfaction:** {a.get('satisfaction_pct', 'N/A')}% | "
            f"**Sentiment Score:** {a.get('sentiment_score', 'N/A')}/100\n",
            f"### ✅ What Customers Love",
            "- " + "\n- ".join(a.get("common_praises", []) or ["No specific praises yet"]),
            f"\n### ❌ Common Complaints",
            "- " + "\n- ".join(a.get("common_complaints", []) or ["No significant complaints"]),
            f"\n### 📝 Summary",
            a.get("summary", ""),
            f"\n**Verdict:** {a.get('recommendation', 'Neutral')}",
        ]
        return "\n".join(lines)


review_agent = ReviewAgent()
