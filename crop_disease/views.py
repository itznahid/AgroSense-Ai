"""
crop_disease/views.py — Enterprise Disease Detection + Commerce Integration
============================================================================
DROP-IN REPLACEMENT for the original views.py.

Preserves every original URL-facing view name:
  • scan_upload   (renders upload form)
  • scan_result   (runs Gemini Vision, renders result + marketplace products)
  • scan_history  (paginated scan list)
  • scan_detail   (full scan detail with commerce)
  • api_predict   (REST JSON endpoint — now returns marketplace_products too)

New enterprise additions in every view:
  ✓ Marketplace product recommendations after disease detection
  ✓ AI narrative linking disease → treatment products
  ✓ Digital Twin update on every scan
  ✓ Full multi-key Gemini failover (via upgraded disease_detector)
"""

import logging

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import CropDiseaseForm
from .models import CropDiseaseScan
from ai_engine.services.disease_detector import (
    DiseaseDetectionError,
    NotAPlantImageError,
    disease_detector,
)

logger = logging.getLogger(__name__)


# ── Upload Page ───────────────────────────────────────────────────────────────

def scan_upload(request):
    """
    GET  → render upload form.
    POST → save image, redirect to scan_result for analysis.
    """
    form = CropDiseaseForm()
    if request.method == "POST":
        form = CropDiseaseForm(request.POST, request.FILES)
        if form.is_valid():
            scan = form.save(commit=False)
            if request.user.is_authenticated:
                scan.user = request.user
            scan.save()
            return redirect("crop_disease:scan_result", pk=scan.pk)
    recent_scans = _get_recent_scans(request.user if request.user.is_authenticated else None)
    return render(request, "crop_disease/scan_upload.html", {
        "form": form,
        "recent_scans": recent_scans,
    })


# ── Scan Result (analysis runs here) ─────────────────────────────────────────

def scan_result(request, pk):
    """
    Run Gemini Vision analysis on a pending scan (lazy — runs on first GET).
    After detection, automatically fetches marketplace treatment products
    and generates an AI product narrative.
    """
    scan = get_object_or_404(CropDiseaseScan, pk=pk)
    _assert_scan_owner(scan, request.user)

    if scan.status == "pending":
        try:
            # FIX: FieldFile.file is None until opened; calling .read() on an
            # unopened FieldFile raises AttributeError: 'NoneType' has no
            # attribute 'read'.  Always open → read → close explicitly.
            scan.image.open("rb")
            try:
                image_bytes = scan.image.read()
            finally:
                scan.image.close()

            mime = _mime_from_name(scan.image.name)
            user = request.user if request.user.is_authenticated else None
            result = disease_detector.analyze(image_bytes, mime_type=mime, user=user)

            # ── Persist detection result ──────────────────────────────────────
            scan.crop_name        = result.get("crop", "")
            scan.predicted_class  = result.get("disease", "")
            scan.confidence       = result.get("confidence", "")
            scan.severity         = result.get("severity", "")
            scan.is_healthy       = result.get("is_healthy", False)
            scan.symptoms         = result.get("symptoms", [])
            scan.causes           = result.get("causes", [])
            scan.treatment_steps  = result.get("treatment", [])
            scan.prevention_tips  = result.get("prevention", [])
            scan.additional_notes = result.get("additional_notes", "")
            scan.status           = "completed"
            # Store commerce data
            scan.marketplace_products = result.get("marketplace_products", [])
            scan.product_narrative    = result.get("product_narrative", "")

        except NotAPlantImageError as exc:
            logger.warning("Non-plant image scan=%s: %s", pk, exc)
            scan.status        = "failed"
            scan.error_message = f"NOT_A_PLANT:{exc}"

        except DiseaseDetectionError as exc:
            logger.error("Disease detection failed scan=%s: %s", pk, exc)
            scan.status        = "failed"
            scan.error_message = str(exc)

        except Exception as exc:
            logger.exception("Unexpected failure scan=%s", pk)
            scan.status        = "failed"
            scan.error_message = str(exc)

        scan.save()

    # ── Digital Twin update ───────────────────────────────────────────────────
    if scan.status == "completed" and request.user.is_authenticated:
        _touch_digital_twin(request.user, scan.predicted_class)

    # ── Fallback: fresh product search if no cached products ─────────────────
    marketplace_products = scan.marketplace_products or []
    if scan.status == "completed" and not marketplace_products:
        marketplace_products = _fetch_treatment_products(scan, request.user)

    return render(request, "crop_disease/scan_result.html", {
        "scan":                  scan,
        "marketplace_products":  marketplace_products,
        "product_narrative":     scan.product_narrative,
        # legacy template key kept for backward compatibility
        "recommended_products":  marketplace_products,
    })


# ── History ───────────────────────────────────────────────────────────────────

# FIX: replaced manual redirect with @login_required so that the ?next=
# parameter is preserved, allowing Django to redirect back after login.
@login_required(login_url="accounts:login")
def scan_history(request):
    """Paginated list of completed scans."""
    qs = CropDiseaseScan.objects.filter(
        user=request.user, status="completed"
    ).order_by("-uploaded_at")
    page_obj = Paginator(qs, 12).get_page(request.GET.get("page"))
    return render(request, "crop_disease/scan_history.html", {"page_obj": page_obj})


# ── Detail ────────────────────────────────────────────────────────────────────

def scan_detail(request, pk):
    """Full detail view for a completed scan with marketplace products."""
    scan = get_object_or_404(CropDiseaseScan, pk=pk)
    _assert_scan_owner(scan, request.user)
    # FIX: use already-cached products from the scan record; only hit the
    # marketplace service when the cache is empty (avoids a redundant network
    # call on every page load).
    marketplace_products = scan.marketplace_products or _fetch_treatment_products(scan, request.user)
    return render(request, "crop_disease/scan_detail.html", {
        "scan":                 scan,
        "marketplace_products": marketplace_products,
        "recommended_products": marketplace_products,  # legacy key
    })


# ── REST API Endpoint ─────────────────────────────────────────────────────────

@require_POST
def api_predict(request):
    """
    POST /disease/api/predict/
    Multipart: key = 'image'
    Returns JSON with full disease analysis + marketplace_products.
    """
    form = CropDiseaseForm(request.POST, request.FILES)
    if not form.is_valid():
        return JsonResponse({"error": form.errors}, status=400)

    scan = form.save(commit=False)
    if request.user.is_authenticated:
        scan.user = request.user
    scan.save()

    try:
        # FIX: same open → read → close pattern as scan_result.
        scan.image.open("rb")
        try:
            image_bytes = scan.image.read()
        finally:
            scan.image.close()

        mime   = _mime_from_name(scan.image.name)
        user   = request.user if request.user.is_authenticated else None
        result = disease_detector.analyze(image_bytes, mime_type=mime, user=user)

        scan.crop_name        = result.get("crop", "")
        scan.predicted_class  = result.get("disease", "")
        scan.confidence       = result.get("confidence", "")
        scan.severity         = result.get("severity", "")
        scan.is_healthy       = result.get("is_healthy", False)
        scan.symptoms         = result.get("symptoms", [])
        scan.causes           = result.get("causes", [])
        scan.treatment_steps  = result.get("treatment", [])
        scan.prevention_tips  = result.get("prevention", [])
        scan.additional_notes = result.get("additional_notes", "")
        scan.marketplace_products = result.get("marketplace_products", [])
        scan.product_narrative    = result.get("product_narrative", "")
        scan.status           = "completed"
        scan.save()

        if request.user.is_authenticated:
            _touch_digital_twin(request.user, scan.predicted_class)

        return JsonResponse({
            "scan_id":              scan.pk,
            "crop":                 result.get("crop"),
            "disease":              result.get("disease"),
            "confidence":           result.get("confidence"),
            "severity":             result.get("severity"),
            "is_healthy":           result.get("is_healthy"),
            "symptoms":             result.get("symptoms", []),
            "causes":               result.get("causes", []),
            "treatment":            result.get("treatment", []),
            "prevention":           result.get("prevention", []),
            "additional_notes":     result.get("additional_notes", ""),
            "marketplace_products": result.get("marketplace_products", []),
            "product_narrative":    result.get("product_narrative", ""),
        })

    except NotAPlantImageError as exc:
        scan.status        = "failed"
        scan.error_message = f"NOT_A_PLANT:{exc}"
        scan.save()
        return JsonResponse({"error": "not_a_plant_image", "detail": str(exc)}, status=422)

    # FIX: DiseaseDetectionError was silently falling through to the generic
    # Exception handler below.  Catch it explicitly so callers get a
    # consistent error shape and the log records the right level.
    except DiseaseDetectionError as exc:
        logger.error("api_predict DiseaseDetectionError scan=%s: %s", scan.pk, exc)
        scan.status        = "failed"
        scan.error_message = str(exc)
        scan.save()
        return JsonResponse({"error": "detection_failed", "detail": str(exc)}, status=500)

    except Exception as exc:
        logger.exception("api_predict failed for scan=%s", scan.pk)
        scan.status        = "failed"
        scan.error_message = str(exc)
        scan.save()
        return JsonResponse({"error": "analysis_failed", "detail": str(exc)}, status=500)


# ── Private helpers ───────────────────────────────────────────────────────────

def _mime_from_name(filename: str) -> str:
    name = (filename or "").lower()
    if name.endswith(".png"):
        return "image/png"
    if name.endswith(".webp"):
        return "image/webp"
    return "image/jpeg"


def _fetch_treatment_products(scan, user) -> list:
    """Query marketplace for treatment products relevant to this scan."""
    try:
        from ai_engine.services.product_search_service import product_search_service
        query = f"{scan.predicted_class or ''} {scan.crop_name or ''} treatment fungicide"
        products = product_search_service.search(query=query, limit=4, user=user)
        return [product_search_service.serialize(p) for p in products]
    except Exception as exc:
        logger.error("_fetch_treatment_products error: %s", exc)
        return []


def _get_recent_scans(user, limit: int = 5):
    try:
        if not user:
            return []
        qs = CropDiseaseScan.objects.filter(
            user=user, status="completed"
        ).order_by("-uploaded_at")
        return qs[:limit]
    except Exception:
        return []


def _assert_scan_owner(scan, user) -> None:
    if scan.user_id and (not user.is_authenticated or scan.user_id != user.pk):
        raise PermissionDenied("This scan does not belong to you.")


def _touch_digital_twin(user, disease_name: str) -> None:
    """Append detected disease to the user's Digital Twin profile."""
    if not disease_name or disease_name.lower() in ("healthy", ""):
        return
    try:
        from ai_engine.models import DigitalTwin
        twin, _ = DigitalTwin.objects.get_or_create(user=user)
        history = list(twin.disease_history or [])
        if disease_name not in history:
            history.append(disease_name)
            twin.disease_history = history[-20:]  # keep last 20
            twin.save(update_fields=["disease_history"])
    except Exception as exc:
        logger.debug("_touch_digital_twin error: %s", exc)
