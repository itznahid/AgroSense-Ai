"""
nutrition_agent.py — Healthy Food & Nutrition Recommendation Agent
===================================================================
Handles all nutrition/diet-related queries:
  - Weight loss / weight gain
  - Diabetes-friendly diet
  - High protein diet
  - Heart-healthy diet
  - Child nutrition
  - Elderly nutrition
  - General healthy eating

Flow:
  1. Detect nutrition goal from query text (fast, no API call)
  2. Call Gemini with NUTRITION_SYSTEM for structured food recommendations (JSON)
  3. Extract marketplace_keywords from AI response
  4. Search AgroSense Marketplace for matching food/produce products
  5. Return formatted markdown response + product cards
"""
from __future__ import annotations

import logging

from ai_engine.agents.orchestrator import AgentResponse
from ai_engine.services.gemini_service import gemini_service
from ai_engine.services.product_search_service import product_search_service
from ai_engine.services.prompt_manager import PromptManager

logger = logging.getLogger(__name__)

# Icons for each nutrition goal
GOAL_ICONS = {
    "weight_loss":       "⚖️",
    "weight_gain":       "💪",
    "diabetes_friendly": "🩺",
    "high_protein":      "🥩",
    "heart_healthy":     "❤️",
    "child_nutrition":   "👶",
    "elderly_nutrition": "👴",
    "general_healthy":   "🥗",
}


class NutritionAgent:
    """
    Generates healthy food recommendations with AgroSense Marketplace integration.
    Every response includes: recommended foods, foods to avoid, meal tips,
    and relevant marketplace product cards.
    """

    def handle(self, user, query: str, context: dict = None) -> AgentResponse:
        context = context or {}

        # 1. Detect nutrition goal locally (no API call needed)
        goal = PromptManager.detect_nutrition_goal(query)

        # 2. Get structured food recommendations from Gemini
        prompt = PromptManager.build_nutrition_prompt(query, goal)
        nutrition_data = gemini_service.generate_json(
            prompt=prompt,
            system_prompt=PromptManager.NUTRITION_SYSTEM,
            temperature=0.4,
            agent_type="nutrition_agent",
        )

        # 3. Search marketplace using AI-suggested keywords
        products = []
        if nutrition_data and isinstance(nutrition_data, dict):
            keywords = nutrition_data.get("marketplace_keywords", [])
            # Combine keywords into a single search query for better results
            search_query = " ".join(keywords[:4]) if keywords else query
            try:
                products = product_search_service.search(
                    query=search_query,
                    limit=4,
                    user=user,
                )
            except Exception as exc:
                logger.warning("NutritionAgent: marketplace search failed: %s", exc)

            # Fallback: search by goal-specific terms if no products found
            if not products:
                fallback_query = self._goal_fallback_query(goal)
                try:
                    products = product_search_service.search(
                        query=fallback_query,
                        limit=4,
                        user=user,
                    )
                except Exception:
                    pass

        # 4. Format the response
        if nutrition_data and isinstance(nutrition_data, dict):
            text = self._format_response(nutrition_data, products)
        else:
            text = self._fallback_response(goal, query)

        return AgentResponse(
            text=text,
            agent_type="nutrition_agent",
            products=products,
            metadata={
                "goal": goal,
                "show_product_cards": bool(products),
            },
        )

    # ── Formatting ─────────────────────────────────────────────────────────────

    @staticmethod
    def _format_response(data: dict, products: list) -> str:
        goal       = data.get("goal", "general_healthy")
        goal_label = data.get("goal_label", "Healthy Diet")
        intro      = data.get("intro", "")
        foods      = data.get("recommended_foods", [])
        avoid      = data.get("foods_to_avoid", [])
        tips       = data.get("meal_tips", [])
        icon       = GOAL_ICONS.get(goal, "🥗")

        lines = [f"## {icon} {goal_label} — Food Recommendations\n"]

        if intro:
            lines.append(f"{intro}\n")

        # Recommended foods
        if foods:
            lines.append("### ✅ Recommended Foods\n")
            for food in foods:
                name         = food.get("name", "")
                benefit      = food.get("benefit", "")
                availability = food.get("local_availability", "")
                avail_badge  = f" *({availability})*" if availability else ""
                lines.append(f"- **{name}**{avail_badge} — {benefit}")
            lines.append("")

        # Foods to avoid
        if avoid:
            lines.append("### ❌ Foods to Avoid\n")
            for item in avoid:
                name   = item.get("name", "")
                reason = item.get("reason", "")
                lines.append(f"- **{name}** — {reason}")
            lines.append("")

        # Meal tips
        if tips:
            lines.append("### 💡 Meal Tips\n")
            for tip in tips:
                lines.append(f"- {tip}")
            lines.append("")

        # Marketplace section
        if products:
            lines.append("### 🛒 Marketplace Recommendations\n")
            lines.append(
                "These AgroSense products are available in our marketplace "
                "and match your dietary needs:"
            )
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _fallback_response(goal: str, query: str) -> str:
        """Simple fallback when Gemini JSON fails."""
        icon  = GOAL_ICONS.get(goal, "🥗")
        label = goal.replace("_", " ").title()
        defaults = {
            "weight_loss":       "Brown rice, oats, lentils (dal), green vegetables, "
                                 "bitter gourd (karela), cucumber, spinach, papaya, guava.",
            "weight_gain":       "Banana, sweet potato, chickpeas, lentils, nuts, "
                                 "milk, eggs, brown rice, dates.",
            "diabetes_friendly": "Brown rice, oats, lentils, green vegetables, "
                                 "bitter gourd (karela), chickpeas, fenugreek, drumstick leaves.",
            "high_protein":      "Lentils (dal), chickpeas, eggs, fish, chicken, "
                                 "soybeans, milk, paneer, nuts.",
            "heart_healthy":     "Oats, brown rice, flaxseeds, garlic, tomato, "
                                 "spinach, olive oil, fish, walnuts.",
            "child_nutrition":   "Milk, eggs, banana, sweet potato, lentils, "
                                 "green vegetables, fish, rice, fruits.",
            "elderly_nutrition": "Oats, soft lentils, banana, papaya, leafy greens, "
                                 "yogurt, fish, whole grains, turmeric milk.",
            "general_healthy":   "Brown rice, lentils, green vegetables, fruits, "
                                 "fish, eggs, milk, whole grains.",
        }
        food_list = defaults.get(goal, defaults["general_healthy"])
        return (
            f"## {icon} {label} — Recommended Foods\n\n"
            f"{food_list}\n\n"
            "Check the Marketplace Recommendations below for available products in AgroSense.\n"
        )

    @staticmethod
    def _goal_fallback_query(goal: str) -> str:
        """Return a fallback search query string for marketplace search per goal."""
        fallback_map = {
            "weight_loss":       "vegetables spinach green bitter gourd",
            "weight_gain":       "banana sweet potato chickpeas lentils",
            "diabetes_friendly": "bitter gourd lentils oats vegetables",
            "high_protein":      "lentils chickpeas soybean protein",
            "heart_healthy":     "oats vegetables garlic flaxseed",
            "child_nutrition":   "banana milk vegetables fruits",
            "elderly_nutrition": "oats banana papaya lentils",
            "general_healthy":   "vegetables fruits lentils organic",
        }
        return fallback_map.get(goal, "vegetables fruits lentils")


# ── Singleton ──────────────────────────────────────────────────────────────────
nutrition_agent = NutritionAgent()
