"""
merchant_agent.py — Merchant AI Assistant Agent
Answers merchant business questions using ONLY their own data.
Strict authorization: cross-merchant data access is BLOCKED.
"""
from __future__ import annotations
from ai_engine.agents.orchestrator import AgentResponse
from ai_engine.services.gemini_service import gemini_service
from ai_engine.services.prompt_manager import PromptManager


class MerchantAgent:
    """
    Handles merchant-specific queries. 
    Authorization enforced: only the merchant's own data is used.
    """

    def handle(self, user, query: str, context: dict = None) -> AgentResponse:
        # Authorization: must be a merchant
        try:
            if not (hasattr(user, "account") and user.account.is_merchant):
                return AgentResponse(
                    text="⛔ This feature is only available to verified merchants.",
                    agent_type="merchant_agent",
                    error=True,
                )
            merchant_account = user.account
        except Exception:
            return AgentResponse(
                text="⛔ Unable to verify merchant status. Please log in again.",
                agent_type="merchant_agent",
                error=True,
            )

        # Get / refresh merchant twin data
        from ai_engine.models import MerchantTwin
        twin = MerchantTwin.get_or_create_for_merchant(merchant_account)
        merchant_data = twin.analytics_cache

        # Generate AI response using ONLY this merchant's data
        prompt = PromptManager.build_merchant_insight_prompt(query, merchant_data)
        text = gemini_service.generate(
            prompt=prompt,
            system_prompt=PromptManager.MERCHANT_TWIN_SYSTEM,
            temperature=0.3,
            agent_type="merchant_agent",
        )

        return AgentResponse(
            text=text or "Unable to generate merchant insights at this time. Please try again.",
            agent_type="merchant_agent",
            metadata={"merchant_id": merchant_account.id, "data_source": "own_data_only"},
        )


merchant_agent = MerchantAgent()
