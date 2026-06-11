"""
forecast_agent.py — Demand Forecasting AI Agent
Generates demand and revenue forecasts for merchants using historical sales data.
"""
from __future__ import annotations
from ai_engine.agents.orchestrator import AgentResponse
from ai_engine.services.gemini_service import gemini_service
from ai_engine.services.forecast_service import forecast_service
from ai_engine.services.prompt_manager import PromptManager


class ForecastAgent:
    """Generates data-driven demand and revenue forecasts from platform data."""

    def handle(self, user, query: str, context: dict = None) -> AgentResponse:
        is_merchant = hasattr(user, "account") and user.account.is_merchant

        if is_merchant:
            # Merchant-specific forecast
            merchant_account = user.account
            forecast_data = forecast_service.build_merchant_forecast(merchant_account)
        else:
            # Platform-wide trend forecast (for general users)
            forecast_data = forecast_service.build_platform_forecast()

        # Build prompt with historical data
        prompt = f"""User question: "{query}"

Forecast data:
{__import__('json').dumps(forecast_data, indent=2)}

Generate a clear, data-driven forecast response. Include:
- Specific percentage changes and time periods
- Key seasonal factors for Bangladesh agriculture
- Actionable recommendations
- Confidence level

Format for {('a merchant' if is_merchant else 'a farmer/buyer')}."""

        text = gemini_service.generate(
            prompt=prompt,
            system_prompt=PromptManager.FORECAST_SYSTEM,
            temperature=0.3,
            agent_type="forecast_agent",
        )

        return AgentResponse(
            text=text or "Forecast data is being analyzed. Please check back shortly.",
            agent_type="forecast_agent",
            metadata={"forecast_data": forecast_data},
        )


forecast_agent = ForecastAgent()
