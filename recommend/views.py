"""
recommend/views.py
==================
Kept for: home page, features page, dashboard, profile, weather API.
The old ML-based predict view now redirects to the Agro AI Assistant.
"""
import logging

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .models import UserProfile
from .weather import fetch_weather, fetch_weather_by_coords

logger = logging.getLogger(__name__)
_LOGIN_URL = "accounts:login"


def _get_or_create_profile(user):
    profile, _ = UserProfile.objects.get_or_create(
        user=user, defaults={"phone": "", "language": "en"}
    )
    return profile


# ── Public views ──────────────────────────────────────────────────────────────

def home(request):
    from marketplace.models import Product
    featured_products = Product.objects.filter(is_active=True).order_by("-rating", "-review_count")[:8]
    return render(request, "recommend/home.html", {"featured_products": featured_products})


def features(request):
    return render(request, "recommend/home.html")


# ── Protected views ───────────────────────────────────────────────────────────

@login_required(login_url=_LOGIN_URL)
def dashboard(request):
    from chatbot.models import ChatSession
    from crop_disease.models import CropDiseaseScan
    profile          = _get_or_create_profile(request.user)
    recent_sessions  = ChatSession.objects.filter(user=request.user)[:5]
    recent_scans     = CropDiseaseScan.objects.filter(user=request.user, status="completed")[:5]
    return render(request, "recommend/dashboard.html", {
        "profile":         profile,
        "recent_sessions": recent_sessions,
        "recent_scans":    recent_scans,
    })


@login_required(login_url=_LOGIN_URL)
def profile_view(request):
    profile = _get_or_create_profile(request.user)
    return render(request, "recommend/profile.html", {"profile": profile})


@login_required(login_url=_LOGIN_URL)
def predict_view(request):
    """Old ML prediction page → redirect to the Agro AI Assistant."""
    return redirect("chatbot:chat_home")


@login_required(login_url=_LOGIN_URL)
def history_view(request):
    """Old history page → redirect to AI Assistant."""
    return redirect("chatbot:chat_home")


# ── Weather API ───────────────────────────────────────────────────────────────

@require_GET
def weather_view(request):
    city = request.GET.get("city", "").strip()
    lat  = request.GET.get("lat")
    lon  = request.GET.get("lon")

    if lat and lon:
        try:
            result = fetch_weather_by_coords(float(lat), float(lon))
        except ValueError:
            return JsonResponse({"ok": False, "error": "Invalid coordinates."}, status=400)
    elif city:
        result = fetch_weather(city)
    else:
        return JsonResponse({"ok": False, "error": "Provide city or lat/lon."}, status=400)

    return JsonResponse(result)
