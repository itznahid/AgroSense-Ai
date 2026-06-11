"""
orchestrator.py — Master AI Agent Router
=========================================
The Orchestrator analyzes user intent and dispatches to the correct specialized
agent. All chatbot requests flow through here.

Intent → Agent mapping:
  marketplace_search   → MarketplaceAgent
  product_comparison   → ComparisonAgent
  review_analysis      → ReviewAgent
  recommendation       → RecommendationAgent
  merchant_analytics   → AnalyticsAgent
  merchant_forecast    → ForecastAgent
  disease_query        → DiseaseAgent
  nutrition_query      → NutritionAgent  (healthy foods, diet, food recommendations)
  general_chat         → CropAgent (general agriculture)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from ai_engine.services.gemini_service import gemini_service
from ai_engine.services.prompt_manager import PromptManager

logger = logging.getLogger(__name__)

# ── Response container ─────────────────────────────────────────────────────────

@dataclass
class AgentResponse:
    """Unified response from any agent."""
    text: str
    agent_type: str = "chat"
    products: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    error: bool = False


# ── Orchestrator ───────────────────────────────────────────────────────────────

class AgentOrchestrator:
    """
    Routes incoming user messages to the correct specialized agent.
    Perform intent classification first, then delegate.
    """

    # ── Intent Classification ──────────────────────────────────────────────────

    def _classify_intent(self, query: str) -> tuple[str, list[str]]:
        """
        Use Gemini to classify the user's intent and extract entities.
        Returns (intent_str, [sub_entities]).
        """
        prompt = PromptManager.build_intent_prompt(query)
        result = gemini_service.generate_json(
            prompt,
            system_prompt=PromptManager.INTENT_CLASSIFICATION_SYSTEM,
            temperature=0.0,
            agent_type="orchestrator",
        )
        if isinstance(result, dict):
            intent = result.get("intent", "general_chat")
            entities = result.get("sub_entities", [])
            return intent, entities
        return "general_chat", []

    # ── Main Route Method ──────────────────────────────────────────────────────

    def route(
        self,
        user,
        query: str,
        session=None,
        history: Optional[list] = None,
        weather_context: str = "",
        context: Optional[dict] = None,
    ) -> AgentResponse:
        """
        Classify intent and route to the correct agent.
        All agents receive the user object for authorization.
        """
        context = context or {}
        intent, entities = self._classify_intent(query)
        logger.info("Orchestrator: user=%s intent=%s query=%.80s", user, intent, query)

        # Check if this is a merchant asking merchant-specific questions
        is_merchant = self._is_merchant(user)
        if intent in ("merchant_analytics", "merchant_forecast") and not is_merchant:
            # Non-merchants shouldn't be routed to merchant agents
            intent = "general_chat"

        if intent == "marketplace_search":
            from ai_engine.agents.marketplace_agent import marketplace_agent
            return marketplace_agent.handle(user, query, context)

        elif intent == "product_comparison":
            from ai_engine.agents.comparison_agent import comparison_agent
            return comparison_agent.handle(user, query, context)

        elif intent == "review_analysis":
            from ai_engine.agents.review_agent import review_agent
            return review_agent.handle(user, query, context)

        elif intent == "recommendation":
            from ai_engine.agents.recommendation_agent import recommendation_agent
            return recommendation_agent.handle(user, query, context)

        elif intent == "merchant_analytics" and is_merchant:
            from ai_engine.agents.analytics_agent import analytics_agent
            return analytics_agent.handle(user, query, context)

        elif intent == "merchant_forecast" and is_merchant:
            from ai_engine.agents.forecast_agent import forecast_agent
            return forecast_agent.handle(user, query, context)

        elif intent == "disease_query":
            from ai_engine.agents.disease_agent import disease_agent
            return disease_agent.handle(user, query, context)

        elif intent == "nutrition_query":
            from ai_engine.agents.nutrition_agent import nutrition_agent
            return nutrition_agent.handle(user, query, context)

        else:
            # Default: general agriculture chat
            from ai_engine.agents.crop_agent import crop_agent
            return crop_agent.handle(
                user, query,
                history=history,
                weather_context=weather_context,
                context=context,
            )

    @staticmethod
    def _is_merchant(user) -> bool:
        """Check if the user has a merchant account."""
        try:
            return hasattr(user, "account") and user.account.is_merchant
        except Exception:
            return False


# ── Singleton ──────────────────────────────────────────────────────────────────
orchestrator = AgentOrchestrator()
