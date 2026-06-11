"""
crop_agent.py — General Agriculture Chat Agent
"""
from __future__ import annotations
from ai_engine.agents.orchestrator import AgentResponse
from ai_engine.services.gemini_service import gemini_service, AGROSENSE_SYSTEM_PROMPT


class CropAgent:
    """Handles general agriculture questions, weather-integrated advice, and crop guidance."""

    def handle(
        self,
        user,
        query: str,
        history: list = None,
        weather_context: str = "",
        context: dict = None,
    ) -> AgentResponse:
        # Enrich with digital twin context if available
        system = AGROSENSE_SYSTEM_PROMPT
        try:
            from ai_engine.models import DigitalTwin
            twin = DigitalTwin.objects.filter(user=user).first()
            if twin and twin.ai_profile:
                crops = ", ".join(twin.crops_grown[:3]) if twin.crops_grown else "not specified"
                cats  = ", ".join(twin.preferred_categories[:3]) if twin.preferred_categories else "general"
                system = (
                    f"{AGROSENSE_SYSTEM_PROMPT}\n\n"
                    f"[User context: grows {crops}; prefers {cats} products; "
                    f"budget: {twin.budget_range}]"
                )
        except Exception:
            pass

        text = gemini_service.chat(
            user_message=query,
            history=history,
            weather_context=weather_context,
            system_prompt=system,
            agent_type="crop_agent",
        )
        return AgentResponse(text=text, agent_type="crop_agent")


crop_agent = CropAgent()
