"""
ai_admin/views.py — AI Monitoring Dashboard & Key Management
=============================================================
Staff-only views for:
  • Real-time Gemini call monitoring
  • API key management (add / edit / delete / test / reorder)
  • Failover event history
  • Agent usage stats
  • System health
"""
from __future__ import annotations

import json
from datetime import timedelta

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Avg, Count, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from ai_engine.models import AICallLog, AIKeyConfig


# ── Dashboard ──────────────────────────────────────────────────────────────────

@staff_member_required
def dashboard(request):
    """Main AI monitoring dashboard."""
    now   = timezone.now()
    since = now - timedelta(hours=24)

    # ── Call stats (last 24 h) ────────────────────────────────────────────────
    logs_24h    = AICallLog.objects.filter(timestamp__gte=since)
    total_calls = logs_24h.count()
    success_cnt = logs_24h.filter(success=True).count()
    fail_cnt    = total_calls - success_cnt
    failovers   = logs_24h.filter(is_failover=True).count()
    avg_latency = logs_24h.filter(success=True).aggregate(a=Avg("latency_ms"))["a"] or 0

    success_rate = round(success_cnt / total_calls * 100, 1) if total_calls else 0.0

    # ── Per-model usage ───────────────────────────────────────────────────────
    model_stats = list(
        logs_24h.values("model_used")
        .annotate(calls=Count("id"), successes=Count("id", filter=__import__("django.db.models", fromlist=["Q"]).Q(success=True)))
        .order_by("-calls")
    )

    # ── Per-agent usage ───────────────────────────────────────────────────────
    agent_stats = list(
        logs_24h.values("agent_type")
        .annotate(calls=Count("id"), avg_lat=Avg("latency_ms"))
        .order_by("-calls")
    )
    for a in agent_stats:
        a["avg_lat"] = round(a["avg_lat"] or 0)

    # ── Recent errors ─────────────────────────────────────────────────────────
    recent_errors = list(
        logs_24h.filter(success=False)
        .values("timestamp", "model_used", "agent_type", "error_type", "key_index")
        .order_by("-timestamp")[:20]
    )

    # ── Key status ────────────────────────────────────────────────────────────
    db_keys = AIKeyConfig.objects.all().order_by("priority")
    keys_data = [
        {
            "obj":           k,
            "success_rate":  k.success_rate(),
            "calls_24h":     logs_24h.filter(db_key_id=k.id).count(),
            "failures_24h":  logs_24h.filter(db_key_id=k.id, success=False).count(),
        }
        for k in db_keys
    ]

    # ── Hourly chart data (last 24 h) ─────────────────────────────────────────
    from django.db.models.functions import TruncHour
    hourly = list(
        logs_24h.annotate(hour=TruncHour("timestamp"))
        .values("hour")
        .annotate(total=Count("id"), success=Count("id", filter=__import__("django.db.models", fromlist=["Q"]).Q(success=True)))
        .order_by("hour")
    )
    chart_labels  = [h["hour"].strftime("%H:%M") for h in hourly]
    chart_total   = [h["total"]   for h in hourly]
    chart_success = [h["success"] for h in hourly]

    # ── System health signal ──────────────────────────────────────────────────
    if success_rate >= 95:
        health_status, health_class = "Healthy",  "success"
    elif success_rate >= 80:
        health_status, health_class = "Degraded", "warning"
    else:
        health_status, health_class = "Critical", "danger"

    # ── Failover timeline (last 50 events) ────────────────────────────────────
    failover_events = list(
        logs_24h.filter(is_failover=True)
        .values("timestamp", "key_index", "model_used", "agent_type", "success")
        .order_by("-timestamp")[:50]
    )

    context = {
        "total_calls":     total_calls,
        "success_cnt":     success_cnt,
        "fail_cnt":        fail_cnt,
        "failovers":       failovers,
        "avg_latency":     round(avg_latency),
        "success_rate":    success_rate,
        "health_status":   health_status,
        "health_class":    health_class,
        "model_stats":     model_stats,
        "agent_stats":     agent_stats,
        "recent_errors":   recent_errors,
        "keys_data":       keys_data,
        "chart_labels":    json.dumps(chart_labels),
        "chart_total":     json.dumps(chart_total),
        "chart_success":   json.dumps(chart_success),
        "failover_events": failover_events,
        "now":             now,
    }
    return render(request, "ai_admin/dashboard.html", context)


# ── Key Management ─────────────────────────────────────────────────────────────

@staff_member_required
def keys_list(request):
    """List all API keys with actions."""
    keys = AIKeyConfig.objects.all().order_by("priority")
    return render(request, "ai_admin/keys_list.html", {"keys": keys})


@staff_member_required
def key_add(request):
    """Add a new Gemini API key."""
    if request.method == "POST":
        name     = request.POST.get("name", "").strip()
        api_key  = request.POST.get("api_key", "").strip()
        priority = int(request.POST.get("priority", 2))
        notes    = request.POST.get("notes", "").strip()

        if not name or not api_key:
            messages.error(request, "Name and API key are required.")
        else:
            AIKeyConfig.objects.create(
                name=name, api_key=api_key, priority=priority, notes=notes
            )
            messages.success(request, f"Key '{name}' added successfully.")
            return redirect("ai_admin:dashboard")

    return render(request, "ai_admin/key_form.html", {"action": "Add"})


@staff_member_required
def key_edit(request, pk):
    """Edit an existing key (name, priority, notes, active status)."""
    key = get_object_or_404(AIKeyConfig, pk=pk)
    if request.method == "POST":
        key.name      = request.POST.get("name", key.name).strip()
        key.priority  = int(request.POST.get("priority", key.priority))
        key.is_active = "is_active" in request.POST
        key.notes     = request.POST.get("notes", key.notes).strip()
        # Only update the actual key value if a new one was provided
        new_key = request.POST.get("api_key", "").strip()
        if new_key:
            key.api_key = new_key
        key.save()
        messages.success(request, f"Key '{key.name}' updated.")
        return redirect("ai_admin:dashboard")
    return render(request, "ai_admin/key_form.html", {"key": key, "action": "Edit"})


@staff_member_required
@require_POST
def key_delete(request, pk):
    key = get_object_or_404(AIKeyConfig, pk=pk)
    name = key.name
    key.delete()
    messages.success(request, f"Key '{name}' deleted.")
    return redirect("ai_admin:dashboard")


@staff_member_required
@require_POST
def key_toggle(request, pk):
    """Enable / disable a key without deleting it."""
    key = get_object_or_404(AIKeyConfig, pk=pk)
    key.is_active = not key.is_active
    key.save(update_fields=["is_active"])
    state = "enabled" if key.is_active else "disabled"
    messages.success(request, f"Key '{key.name}' {state}.")
    return redirect("ai_admin:dashboard")


@staff_member_required
@require_POST
def key_test(request, pk):
    """Test a specific API key and return result as JSON."""
    key = get_object_or_404(AIKeyConfig, pk=pk)
    from ai_engine.services.gemini_service import gemini_service
    success, message = gemini_service.test_key(key.api_key)
    return JsonResponse({"success": success, "message": message, "key_name": key.name})


@staff_member_required
@require_POST
def key_reorder(request):
    """Reorder keys via AJAX — receives {key_id: new_priority, ...}."""
    try:
        data = json.loads(request.body)
        for key_id, new_priority in data.items():
            AIKeyConfig.objects.filter(pk=int(key_id)).update(priority=int(new_priority))
        return JsonResponse({"success": True})
    except Exception as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=400)


# ── Live Stats API (for dashboard auto-refresh) ────────────────────────────────

@staff_member_required
def live_stats(request):
    """Return real-time stats as JSON for dashboard polling."""
    since = timezone.now() - timedelta(minutes=5)
    logs  = AICallLog.objects.filter(timestamp__gte=since)
    total = logs.count()
    ok    = logs.filter(success=True).count()
    return JsonResponse({
        "calls_5m":     total,
        "success_5m":   ok,
        "fail_5m":      total - ok,
        "failovers_5m": logs.filter(is_failover=True).count(),
        "avg_lat_5m":   round(logs.filter(success=True).aggregate(a=Avg("latency_ms"))["a"] or 0),
        "active_key":   AIKeyConfig.objects.filter(is_active=True).order_by("priority").values_list("name", flat=True).first() or "None",
    })
