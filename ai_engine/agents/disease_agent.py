"""
disease_agent.py — Text-based Disease Query Agent
Handles "What is rice blast?" / "How to treat leaf curl?" type questions.
Image analysis is handled separately by DiseaseDetector + crop_disease app.
"""
from __future__ import annotations
from ai_engine.agents.orchestrator import AgentResponse
from ai_engine.services.gemini_service import gemini_service
from ai_engine.services.product_search_service import product_search_service

DISEASE_SYSTEM = """You are AgroSense Plant Disease Expert AI.
You specialize in plant pathology, disease identification, and agricultural treatment.
Always structure your answers with: Disease Overview, Symptoms, Causes, Treatment Steps,
Prevention, and Recommended Product Types.
Provide practical, actionable advice for farmers in Bangladesh/South Asia."""


class DiseaseAgent:
    """Handles text-based disease queries and links to marketplace products."""

    def handle(self, user, query: str, context: dict = None) -> AgentResponse:
        # Get AI disease answer
        text = gemini_service.chat(
            user_message=query,
            system_prompt=DISEASE_SYSTEM,
            agent_type="disease_agent",
            temperature=0.4,
        )

        # Search for relevant treatment products
        products = []
        try:
            products = product_search_service.search(
                query=query, limit=4, user=user
            )
        except Exception:
            pass

        return AgentResponse(
            text=text,
            agent_type="disease_agent",
            products=products,
            metadata={"show_product_cards": True},
        )


disease_agent = DiseaseAgent()
