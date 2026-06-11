"""
digital_twin_agent.py — Customer Digital Twin Agent
Manages and presents a user's evolving AI behavioral profile.
"""
from __future__ import annotations
from ai_engine.agents.orchestrator import AgentResponse
from ai_engine.services.gemini_service import gemini_service
from ai_engine.services.prompt_manager import PromptManager


class DigitalTwinAgent:
    """Builds and interprets the Customer Digital Twin for personalization."""

    def handle(self, user, query: str = "", context: dict = None) -> AgentResponse:
        from ai_engine.models import DigitalTwin
        twin = DigitalTwin.get_or_create_for_user(user)

        # Generate AI-interpreted profile narrative
        prompt = PromptManager.build_twin_profile_prompt(twin.ai_profile)
        interpreted = gemini_service.generate_json(
            prompt=prompt,
            system_prompt=PromptManager.DIGITAL_TWIN_SYSTEM,
            temperature=0.3,
            agent_type="digital_twin_agent",
        )

        if interpreted:
            summary = interpreted.get("summary", "Profile being built...")
            hints = interpreted.get("recommendation_hints", [])
            text = (
                f"## 🧠 Your AI Farming Profile\n\n{summary}\n\n"
                + ("**Smart hints:**\n- " + "\n- ".join(hints) if hints else "")
            )
        else:
            text = f"Your AI profile is building. You've made {twin.total_orders} purchases so far."

        return AgentResponse(
            text=text,
            agent_type="digital_twin_agent",
            metadata={"twin_id": twin.id, "profile": twin.ai_profile},
        )


digital_twin_agent = DigitalTwinAgent()
