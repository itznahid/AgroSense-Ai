"""
chatbot/views.py — Enterprise AI Chatbot (Orchestrator-powered)
================================================================
All messages route through AgentOrchestrator for intent-based dispatch.
Supports: general chat, product search, comparisons, reviews,
          recommendations, merchant analytics, and forecasting.
"""
from __future__ import annotations

import json
import logging

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)


# ── Chat Page ─────────────────────────────────────────────────────────────────

@login_required
def chat_page(request):
    """Render the main chat interface."""
    from chatbot.models import ChatSession
    # Get or create active session
    session = _get_or_create_session(request.user)
    sessions = (
        ChatSession.objects.filter(user=request.user)
        .order_by("-updated_at")[:10]
    )
    return render(request, "chatbot/chat.html", {
        "session":  session,
        "sessions": sessions,
        "is_merchant": _is_merchant(request.user),
    })


# ── Send Message ──────────────────────────────────────────────────────────────

@login_required
@require_POST
def send_message(request):
    """
    Receive a user message, route through orchestrator, persist, return JSON.

    POST body (JSON):
      { "message": "...", "session_id": N (optional), "weather_context": "..." }

    Returns JSON:
      {
        "success":    true,
        "text":       "AI response markdown",
        "agent_type": "marketplace_agent | crop_agent | ...",
        "products":   [...] | null,
        "session_id": N,
        "message_id": N,
      }
    """
    try:
        body      = json.loads(request.body)
        user_msg  = body.get("message", "").strip()
        session_id = body.get("session_id")
        weather   = body.get("weather_context", "")
    except (json.JSONDecodeError, KeyError):
        return JsonResponse({"success": False, "error": "Invalid request."}, status=400)

    if not user_msg:
        return JsonResponse({"success": False, "error": "Empty message."}, status=400)

    # ── Session ────────────────────────────────────────────────────────────────
    from chatbot.models import ChatSession, ChatMessage
    if session_id:
        session = ChatSession.objects.filter(pk=session_id, user=request.user).first()
        if session is None:
            session = _get_or_create_session(request.user)
    else:
        session = _get_or_create_session(request.user)

    # ── Save user message ──────────────────────────────────────────────────────
    ChatMessage.objects.create(session=session, role="user", content=user_msg)

    # ── Fetch history for context (last 12 turns) ──────────────────────────────
    recent = ChatMessage.objects.filter(session=session).order_by("-created_at")[:12]
    from ai_engine.services.prompt_manager import PromptManager
    history = PromptManager.build_history_for_gemini(reversed(list(recent)))
    # Remove last entry (it's the message we just saved; will be passed as the prompt itself)
    if history and history[-1]["role"] == "user":
        history = history[:-1]

    # ── Route through orchestrator ────────────────────────────────────────────
    from ai_engine.agents.orchestrator import orchestrator
    response = orchestrator.route(
        user            = request.user,
        query           = user_msg,
        session         = session,
        history         = history,
        weather_context = weather,
    )

    # ── Save AI reply ─────────────────────────────────────────────────────────
    ai_msg = ChatMessage.objects.create(
        session   = session,
        role      = "assistant",
        content   = response.text,
        agent_type = response.agent_type,
    )

    # Auto-title session after first exchange
    if ChatMessage.objects.filter(session=session).count() == 2:
        session.title = user_msg[:60]
        session.save(update_fields=["title", "updated_at"])

    # Serialise products for JSON response
    products_data = None
    if response.products:
        from ai_engine.services.product_search_service import product_search_service
        products_data = [product_search_service.serialize(p) for p in response.products]

    return JsonResponse({
        "success":    True,
        "text":       response.text,
        "agent_type": response.agent_type,
        "products":   products_data,
        "metadata":   response.metadata,
        "session_id": session.pk,
        "message_id": ai_msg.pk,
    })


# ── Session Management ────────────────────────────────────────────────────────

@login_required
@require_POST
def new_session(request):
    """Create a new chat session."""
    from chatbot.models import ChatSession
    # Close existing active session
    ChatSession.objects.filter(user=request.user, is_active=True).update(is_active=False)
    session = ChatSession.objects.create(user=request.user, title="New Conversation", is_active=True)
    return JsonResponse({"session_id": session.pk, "title": session.title})


@login_required
def session_history(request, session_id):
    """Return message history for a session as JSON."""
    from chatbot.models import ChatSession, ChatMessage
    session = get_object_or_404(ChatSession, pk=session_id, user=request.user)
    messages = ChatMessage.objects.filter(session=session).order_by("created_at")
    return JsonResponse({
        "session_id": session.pk,
        "title":      session.title,
        "messages": [
            {
                "id":         m.pk,
                "role":       m.role,
                "content":    m.content,
                "agent_type": getattr(m, "agent_type", ""),
                "created_at": m.created_at.strftime("%H:%M"),
            }
            for m in messages
        ],
    })


@login_required
@require_POST
def delete_session(request, session_id):
    """Delete a chat session and its messages."""
    from chatbot.models import ChatSession
    session = get_object_or_404(ChatSession, pk=session_id, user=request.user)
    session.delete()
    return JsonResponse({"success": True})


# ── Digital Twin Profile API ──────────────────────────────────────────────────

@login_required
def my_profile(request):
    """Return user's Digital Twin profile as JSON."""
    try:
        from ai_engine.models import DigitalTwin
        twin = DigitalTwin.get_or_create_for_user(request.user)
        return JsonResponse({
            "success":      True,
            "crops":        twin.crops_grown,
            "categories":   twin.preferred_categories,
            "budget":       twin.budget_range,
            "total_orders": twin.total_orders,
            "diseases":     twin.disease_history,
            "frequency":    twin.purchase_frequency,
        })
    except Exception as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=500)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_or_create_session(user):
    from chatbot.models import ChatSession
    with transaction.atomic():
        session = ChatSession.objects.filter(user=user, is_active=True).order_by("-updated_at").first()
        if session:
            ChatSession.objects.filter(user=user, is_active=True).exclude(pk=session.pk).update(is_active=False)
            return session
        session = ChatSession.objects.create(user=user, title="New Conversation", is_active=True)
    return session


def _is_merchant(user) -> bool:
    try:
        return hasattr(user, "account") and user.account.is_merchant
    except Exception:
        return False
