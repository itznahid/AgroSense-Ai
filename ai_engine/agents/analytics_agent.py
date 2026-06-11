"""
analytics_agent.py — Merchant Analytics AI Agent
Answers detailed sales, revenue, and performance queries for authenticated merchants.
"""
from __future__ import annotations
from ai_engine.agents.orchestrator import AgentResponse
from ai_engine.services.gemini_service import gemini_service
from ai_engine.services.analytics_service import analytics_service
from ai_engine.services.prompt_manager import PromptManager


class AnalyticsAgent:
    """
    Provides deep analytics for merchants: sales totals, growth rates,
    top products, best customers, and conversion metrics.
    """

    def handle(self, user, query: str, context: dict = None) -> AgentResponse:
        # Authorization
        try:
            if not (hasattr(user, "account") and user.account.is_merchant):
                return AgentResponse(
                    text="⛔ Analytics are only available to verified merchants.",
                    agent_type="analytics_agent",
                    error=True,
                )
            merchant_account = user.account
        except Exception:
            return AgentResponse(
                text="⛔ Authentication error.", agent_type="analytics_agent", error=True
            )

        # Build detailed analytics
        data = analytics_service.build_analytics(merchant_account)
        prompt = PromptManager.build_analytics_prompt(query, data)
        text = gemini_service.generate(
            prompt=prompt,
            system_prompt=PromptManager.MERCHANT_TWIN_SYSTEM,
            temperature=0.2,
            agent_type="analytics_agent",
        )

        return AgentResponse(
            text=text or "Analytics data is available but AI summary is temporarily unavailable.",
            agent_type="analytics_agent",
            metadata={"analytics": data},
        )


analytics_agent = AnalyticsAgent()
