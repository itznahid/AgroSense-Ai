"""
GeminiService — Enterprise Multi-Key Reliability Layer
=======================================================
Central gateway for all Google Gemini API calls in AgroSense Enterprise.

Key features:
  • 3-key priority rotation (Primary → Secondary → Emergency Backup)
  • Model fallback:  gemini-2.5-flash → gemini-2.0-flash → gemini-1.5-flash
  • Exponential backoff:  0 s → 2 s → 4 s → 8 s
  • Automatic failover on: 429, 500, 502, 503, 504, timeout, quota exceeded
  • DB-backed key management (AIKeyConfig) with settings.py fallback
  • Metrics logging to AICallLog for admin monitoring dashboard
  • Users NEVER see Gemini errors, quota messages, or stack traces
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from typing import Any, Callable, Optional

from django.conf import settings

logger = logging.getLogger(__name__)

# ── Model priority chain ───────────────────────────────────────────────────────
MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
]

# Exponential backoff delays (seconds) — index 0 = first attempt (no wait)
RETRY_DELAYS = [0, 2, 4, 8]

# HTTP / gRPC status codes that should trigger key/model rotation
RETRYABLE_CODES = frozenset([429, 500, 502, 503, 504])

# String patterns that also indicate retryable conditions
RETRYABLE_PATTERNS = (
    "quota", "rate limit", "too many requests", "resource exhausted",
    "internal error", "bad gateway", "service unavailable", "gateway timeout",
    "timeout", "deadline", "overloaded", "unavailable", "recitation",
)

# ── Agriculture-only system prompt ────────────────────────────────────────────
AGROSENSE_SYSTEM_PROMPT = """You are AgroSense AI, an expert agricultural assistant for Bangladesh and South Asia.

Your expertise covers:
- Crop cultivation, seasonal planning, and agronomy
- Soil science, soil health, and fertilization
- Organic and chemical fertilizers (NPK, compost, micronutrients)
- Irrigation techniques: drip, sprinkler, flood, and water management
- Integrated pest management and pesticide application
- Plant pathology: disease identification, diagnosis, treatment, prevention
- Weather impact on crops and farm management decisions
- Sustainable and environmentally responsible farming practices
- Livestock farming and animal husbandry
- Post-harvest handling, storage, and value chains
- Agricultural economics, market pricing, and demand trends
- Food nutrition, healthy eating, and dietary guidance using locally grown produce
- Nutritional value of crops and food items grown and sold in Bangladesh/South Asia

Rules:
1. Answer agriculture-related questions AND food/nutrition/dietary questions.
2. If a question is completely unrelated to agriculture, farming, food, nutrition, or health
   through food, respond EXACTLY with:
   "I am AgroSense AI and can only assist with agriculture, crops, farming, livestock,
   irrigation, fertilizers, pesticides, soil management, plant diseases, and food nutrition."
3. Give practical, farmer-friendly and consumer-friendly advice that is immediately actionable.
4. When weather data is provided in [Current Weather Context: ...], incorporate it naturally.
5. For plant diseases: always cover symptoms, causes, treatment, and prevention.
6. Return concise but complete answers. Use bullet points or numbered lists where appropriate.
7. Suggest relevant farming or food products whenever applicable.
8. Prioritize safety, food security, and environmentally responsible practices.
9. Use BDT (Taka) for pricing context when relevant. Consider local South Asian context.
10. Format responses with clear structure using markdown where appropriate.
"""


# ── User-facing fallback messages ─────────────────────────────────────────────
_FALLBACK_CHAT = (
    "⚠️ I'm temporarily unavailable. Our AI service is experiencing high demand. "
    "Please try again in a moment."
)
_FALLBACK_EMPTY = ""


class GeminiService:
    """
    Thread-safe singleton wrapping google-genai with enterprise reliability.
    All Gemini calls in AgroSense MUST go through this class.
    """

    _lock = threading.Lock()
    _clients: dict[str, Any] = {}   # api_key -> google-genai Client
    _genai = None
    _types = None

    def _load_genai(self):
        if self._genai and self._types:
            return self._genai, self._types
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise RuntimeError(
                "google-genai is not installed. Install requirements.txt or disable Gemini features."
            ) from exc
        self._genai = genai
        self._types = types
        return genai, types

    # ── Key resolution ─────────────────────────────────────────────────────────

    def _get_keys_from_db(self) -> list[tuple[str, int, str]]:
        """Return [(api_key, db_id, label), …] from AIKeyConfig, ordered by priority."""
        try:
            from ai_engine.models import AIKeyConfig  # lazy import — avoids AppRegistry issues
            rows = (
                AIKeyConfig.objects
                .filter(is_active=True)
                .order_by("priority")
                .values_list("api_key", "id", "name")
            )
            return [(r[0].strip(), r[1], r[2]) for r in rows if r[0].strip()]
        except Exception:
            return []

    def _get_keys_from_settings(self) -> list[tuple[str, None, str]]:
        """Return keys from settings.py / environment variables as fallback."""
        keys: list[tuple[str, None, str]] = []
        for i in range(1, 4):
            raw = (
                getattr(settings, f"GEMINI_API_KEY_{i}", "")
                or os.getenv(f"GEMINI_API_KEY_{i}", "")
            )
            if raw and raw.strip():
                keys.append((raw.strip(), None, f"Key {i}"))
        if not keys:
            single = (
                getattr(settings, "GEMINI_API_KEY", "")
                or os.getenv("GEMINI_API_KEY", "")
            )
            if single and single.strip():
                keys.append((single.strip(), None, "Primary Key"))
        return keys

    def _get_keys(self) -> list[tuple[str, Optional[int], str]]:
        """DB keys take priority; fall back to settings.py / .env."""
        db = self._get_keys_from_db()
        return db if db else self._get_keys_from_settings()

    def _get_client(self, api_key: str) -> Any:
        genai, _types = self._load_genai()
        with self._lock:
            if api_key not in self._clients:
                self._clients[api_key] = genai.Client(api_key=api_key)
            return self._clients[api_key]

    # ── Metrics logging ────────────────────────────────────────────────────────

    def _log_call(
        self,
        key_index: int,
        db_key_id: Optional[int],
        model: str,
        success: bool,
        error_type: str = "",
        latency_ms: int = 0,
        agent_type: str = "",
        is_failover: bool = False,
    ) -> None:
        """Write one row to AICallLog — failures here must never break the app."""
        try:
            from ai_engine.models import AICallLog, AIKeyConfig
            AICallLog.objects.create(
                key_index=key_index,
                db_key_id=db_key_id,
                model_used=model,
                success=success,
                error_type=error_type[:200] if error_type else "",
                latency_ms=latency_ms,
                agent_type=agent_type,
                is_failover=is_failover,
            )
            # Update last_used on the key record
            if db_key_id and success:
                AIKeyConfig.objects.filter(id=db_key_id).update(
                    last_used_at=__import__("django.utils.timezone", fromlist=["now"]).now()
                    if False else __import__("django.utils", fromlist=["timezone"]).timezone.now()
                )
        except Exception:
            pass  # Logging failure must never surface

    # ── Retryability check ─────────────────────────────────────────────────────

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        """Return True if this exception warrants key/model rotation."""
        for attr in ("status_code", "code", "http_status"):
            code = getattr(exc, attr, None)
            if code in RETRYABLE_CODES:
                return True
        msg = str(exc).lower()
        return any(p in msg for p in RETRYABLE_PATTERNS)

    # ── Core failover loop ─────────────────────────────────────────────────────

    def _call_with_failover(
        self,
        call_fn: Callable[[Any, str], str],
        agent_type: str = "",
    ) -> Optional[str]:
        """
        Execute call_fn(client, model_name) → str, trying every key × model
        combination with exponential backoff.

        Returns the first successful response text, or None if all fail.
        """
        keys = self._get_keys()
        if not keys:
            logger.error("No Gemini API keys configured.")
            return None

        first_call = True
        for key_idx, (api_key, db_key_id, key_label) in enumerate(keys):
            client = self._get_client(api_key)
            for model in MODELS:
                for attempt, delay in enumerate(RETRY_DELAYS):
                    if delay:
                        time.sleep(delay)
                    is_failover = not first_call
                    first_call = False
                    t0 = time.monotonic()
                    try:
                        result = call_fn(client, model)
                        latency = int((time.monotonic() - t0) * 1000)
                        self._log_call(
                            key_index=key_idx,
                            db_key_id=db_key_id,
                            model=model,
                            success=True,
                            latency_ms=latency,
                            agent_type=agent_type,
                            is_failover=is_failover,
                        )
                        if is_failover:
                            logger.info(
                                "Gemini failover succeeded: key=%s model=%s attempt=%d",
                                key_label, model, attempt,
                            )
                        return result

                    except Exception as exc:
                        latency = int((time.monotonic() - t0) * 1000)
                        error_type = type(exc).__name__
                        logger.warning(
                            "Gemini call failed | key=%s model=%s attempt=%d | %s: %s",
                            key_label, model, attempt, error_type, exc,
                        )
                        self._log_call(
                            key_index=key_idx,
                            db_key_id=db_key_id,
                            model=model,
                            success=False,
                            error_type=error_type,
                            latency_ms=latency,
                            agent_type=agent_type,
                            is_failover=is_failover,
                        )
                        if not self._is_retryable(exc):
                            # Non-transient error: skip remaining retries for this model
                            break
                        # else: continue retry loop (next delay)

        logger.error("All Gemini keys/models exhausted for agent_type=%s", agent_type)
        return None

    # ── Public API ─────────────────────────────────────────────────────────────

    def chat(
        self,
        user_message: str,
        history: Optional[list] = None,
        weather_context: str = "",
        system_prompt: str = AGROSENSE_SYSTEM_PROMPT,
        agent_type: str = "chat",
        temperature: float = 0.7,
    ) -> str:
        """Multi-turn conversation with optional weather context and history."""
        message = (
            f"[Current Weather Context: {weather_context}]\n\n{user_message}"
            if weather_context else user_message
        )

        def call_fn(client: Any, model: str) -> str:
            _genai, types = self._load_genai()
            contents = []
            if history:
                for entry in history:
                    role = entry.get("role", "user")
                    parts = [types.Part.from_text(text=p) for p in entry.get("parts", [])]
                    contents.append(types.Content(role=role, parts=parts))
            contents.append(
                types.Content(role="user", parts=[types.Part.from_text(text=message)])
            )
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=temperature,
                ),
            )
            return response.text

        return self._call_with_failover(call_fn, agent_type=agent_type) or _FALLBACK_CHAT

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        agent_type: str = "",
    ) -> str:
        """Single-turn text generation for AI agents."""
        def call_fn(client: Any, model: str) -> str:
            _genai, types = self._load_genai()
            config = types.GenerateContentConfig(temperature=temperature)
            if system_prompt:
                config = types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=temperature,
                )
            response = client.models.generate_content(
                model=model, contents=prompt, config=config
            )
            return response.text

        return self._call_with_failover(call_fn, agent_type=agent_type) or _FALLBACK_EMPTY

    def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        agent_type: str = "",
    ) -> Optional[dict | list]:
        """Generate a JSON response, stripping markdown fences if present."""
        raw = self.generate(prompt, system_prompt, temperature, agent_type)
        if not raw:
            return None
        cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip())
        cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            logger.error("JSON parse failed for agent=%s | raw: %.400s", agent_type, raw)
            return None

    def analyze_image(
        self,
        image_bytes: bytes,
        prompt: str,
        mime_type: str = "image/jpeg",
        agent_type: str = "vision",
    ) -> str:
        """Vision inference: analyze an image with a text prompt."""
        def call_fn(client: Any, model: str) -> str:
            _genai, types = self._load_genai()
            image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
            response = client.models.generate_content(
                model=model,
                contents=[
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=prompt), image_part],
                    )
                ],
            )
            return response.text

        return self._call_with_failover(call_fn, agent_type=agent_type) or _FALLBACK_EMPTY

    def analyze_image_json(
        self,
        image_bytes: bytes,
        prompt: str,
        mime_type: str = "image/jpeg",
        agent_type: str = "vision",
    ) -> Optional[dict]:
        """Vision inference returning a parsed JSON dict."""
        raw = self.analyze_image(image_bytes, prompt, mime_type, agent_type)
        if not raw:
            return None
        cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip())
        cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            logger.error("Vision JSON parse failed: %.400s", raw)
            return None

    # ── Convenience method (legacy compatibility) ──────────────────────────────

    def extract_crop_intent(self, user_query: str) -> dict:
        """Extract crop/intent from a natural language query."""
        prompt = f"""Extract agricultural intent from this query.
Return ONLY valid JSON:
{{
  "crop": "crop name or null",
  "intent": "fertilizer|pesticide|seed|fungicide|irrigation|null",
  "keywords": ["keyword1", "keyword2"],
  "is_agricultural": true or false
}}

Query: "{user_query}"

Respond with JSON only."""
        result = self.generate_json(prompt, agent_type="intent_extract")
        if isinstance(result, dict):
            return result
        return {"crop": None, "intent": None, "keywords": [], "is_agricultural": True}

    def analyze_crop_disease(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
        """Legacy disease analysis — delegates to analyze_image_json."""
        from ai_engine.services.prompt_manager import PromptManager
        prompt = PromptManager.DISEASE_ANALYSIS_PROMPT
        result = self.analyze_image_json(image_bytes, prompt, mime_type, agent_type="disease")
        if result is None:
            return {"error": "API_ERROR", "message": "Disease analysis failed. Please try again."}
        return result

    # ── Admin utilities ────────────────────────────────────────────────────────

    def test_key(self, api_key: str) -> tuple[bool, str]:
        """
        Test a specific API key by making a minimal Gemini call.
        Returns (success: bool, message: str).
        """
        try:
            genai, types = self._load_genai()
            client = genai.Client(api_key=api_key.strip())
            response = client.models.generate_content(
                model=MODELS[-1],  # Use the most permissive model for testing
                contents="Reply with the single word: OK",
                config=types.GenerateContentConfig(temperature=0.0, max_output_tokens=5),
            )
            return True, f"Key valid. Model response: {response.text.strip()}"
        except Exception as exc:
            return False, f"Key invalid: {type(exc).__name__}: {exc}"

    def get_active_key_label(self) -> str:
        """Return the label of the first active key (for admin display)."""
        keys = self._get_keys()
        return keys[0][2] if keys else "None configured"


# Module-level singleton — import this everywhere
gemini_service = GeminiService()
