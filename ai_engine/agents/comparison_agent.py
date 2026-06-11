"""
comparison_agent.py — Product Comparison Agent
Compares two or more real marketplace products with structured scoring.
"""
from __future__ import annotations
import json
import re
from ai_engine.agents.orchestrator import AgentResponse
from ai_engine.services.gemini_service import gemini_service
from ai_engine.services.product_search_service import product_search_service
from ai_engine.services.comparison_service import comparison_service
from ai_engine.services.prompt_manager import PromptManager


class ComparisonAgent:
    """
    Extracts product names from the query, fetches real DB data,
    and generates a structured comparison with scores.
    """

    def handle(self, user, query: str, context: dict = None) -> AgentResponse:
        # 1. Extract product names from query
        product_names = self._extract_product_names(query)

        # 2. Find matching products in DB (up to 2)
        if len(product_names) >= 2:
            products = []
            for name in product_names[:2]:
                matches = product_search_service.search(query=name, limit=1, user=user)
                if matches:
                    products.append(matches[0])
        else:
            # If no specific names, find top 2 matching the general query
            products = product_search_service.search(query=query, limit=2, user=user)

        if len(products) < 2:
            return AgentResponse(
                text=(
                    "I need at least two products to compare. "
                    "Please specify the product names, e.g.: "
                    "*'Compare Tricyclazole fungicide and Carbendazim fungicide'*"
                ),
                agent_type="comparison_agent",
                products=products,
            )

        # 3. Enrich with review data
        product_a_data = comparison_service.enrich_product(products[0])
        product_b_data = comparison_service.enrich_product(products[1])

        # 4. Get AI comparison
        prompt = PromptManager.build_comparison_prompt(product_a_data, product_b_data)
        comparison_json = gemini_service.generate_json(
            prompt=prompt,
            system_prompt=PromptManager.COMPARISON_SYSTEM,
            temperature=0.2,
            agent_type="comparison_agent",
        )

        # 5. Format response
        if comparison_json and isinstance(comparison_json, dict):
            text = self._format_comparison(comparison_json, products[0].name, products[1].name)
        else:
            text = self._fallback_comparison(product_a_data, product_b_data)

        return AgentResponse(
            text=text,
            agent_type="comparison_agent",
            products=products,
            metadata={"comparison": comparison_json or {}, "type": "product_comparison"},
        )

    def _extract_product_names(self, query: str) -> list[str]:
        """Use Gemini to extract product names from comparison query."""
        prompt = f"""Extract the two product names being compared in this query.
Return ONLY JSON: {{"product_a": "name or null", "product_b": "name or null"}}
Query: "{query}" """
        result = gemini_service.generate_json(prompt, temperature=0.0, agent_type="comparison_agent")
        if isinstance(result, dict):
            names = [result.get("product_a"), result.get("product_b")]
            return [n for n in names if n]
        return []

    @staticmethod
    def _format_comparison(data: dict, name_a: str, name_b: str) -> str:
        winner = data.get("winner", "Tie")
        reasoning = data.get("reasoning", "")
        a = data.get("product_a", {})
        b = data.get("product_b", {})

        lines = [
            f"## 🔍 Product Comparison: {name_a} vs {name_b}\n",
            f"### {name_a}",
            f"**Pros:** {', '.join(a.get('pros', [])[:3])}",
            f"**Cons:** {', '.join(a.get('cons', [])[:2])}",
            f"Value: {a.get('value_score', 'N/A')}/10 | Performance: {a.get('performance_score', 'N/A')}/10 | "
            f"Popularity: {a.get('popularity_score', 'N/A')}/10\n",
            f"### {name_b}",
            f"**Pros:** {', '.join(b.get('pros', [])[:3])}",
            f"**Cons:** {', '.join(b.get('cons', [])[:2])}",
            f"Value: {b.get('value_score', 'N/A')}/10 | Performance: {b.get('performance_score', 'N/A')}/10 | "
            f"Popularity: {b.get('popularity_score', 'N/A')}/10\n",
            f"### 🏆 Winner: {winner}",
            reasoning,
        ]
        best_for = data.get("best_for", {})
        if best_for:
            lines.append(
                f"\n**Best for {name_a}:** {best_for.get('product_a', '')}"
            )
            lines.append(
                f"**Best for {name_b}:** {best_for.get('product_b', '')}"
            )
        return "\n".join(lines)

    @staticmethod
    def _fallback_comparison(a: dict, b: dict) -> str:
        return (
            f"**{a['name']}** — ৳{a['price']} | Rating: {a['rating']}★ | Stock: {a['stock']}\n\n"
            f"**{b['name']}** — ৳{b['price']} | Rating: {b['rating']}★ | Stock: {b['stock']}\n\n"
            f"Based on price and ratings, "
            f"{'**' + a['name'] + '**' if float(a['rating']) >= float(b['rating']) else '**' + b['name'] + '**'}"
            f" appears to be the better choice."
        )


comparison_agent = ComparisonAgent()
