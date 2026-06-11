from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class CropDiseaseScan(models.Model):
    """Stores each plant disease scan submitted by a user — powered by Gemini Vision."""

    # -- Upload ----------------------------------------------------------------
    user        = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="crop_disease_scans",
        null=True,
        blank=True,
    )
    image       = models.ImageField(upload_to="uploads/crop_disease/%Y/%m/%d/")
    uploaded_at = models.DateTimeField(default=timezone.now)

    # -- Gemini Vision Results -------------------------------------------------
    crop_name        = models.CharField(max_length=200, blank=True)
    predicted_class  = models.CharField(max_length=200, blank=True)   # disease name
    confidence       = models.CharField(max_length=20, blank=True)    # High/Medium/Low
    severity         = models.CharField(max_length=50, blank=True)    # Critical/High/Moderate/Low/None
    is_healthy       = models.BooleanField(null=True, blank=True)

    # Structured JSON arrays from Gemini
    symptoms         = models.JSONField(default=list, blank=True)
    causes           = models.JSONField(default=list, blank=True)
    treatment_steps  = models.JSONField(default=list, blank=True)
    prevention_tips  = models.JSONField(default=list, blank=True)
    additional_notes = models.TextField(blank=True)
    marketplace_products = models.JSONField(default=list, blank=True)
    product_narrative    = models.TextField(blank=True)

    # -- Status ----------------------------------------------------------------
    STATUS_CHOICES = [
        ("pending",   "Pending"),
        ("completed", "Completed"),
        ("failed",    "Failed"),
    ]
    status        = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    error_message = models.TextField(blank=True)

    class Meta:
        ordering     = ["-uploaded_at"]
        verbose_name = "Crop Disease Scan"
        verbose_name_plural = "Crop Disease Scans"
        indexes = [
            models.Index(fields=["user", "status", "-uploaded_at"]),
            models.Index(fields=["status", "-uploaded_at"]),
        ]

    def __str__(self):
        label = self.predicted_class or "Pending"
        return f"Scan #{self.pk} — {label} ({self.uploaded_at:%Y-%m-%d %H:%M})"

    @property
    def confidence_display(self):
        return self.confidence if self.confidence else "—"

    @property
    def severity_badge_color(self):
        return {
            "Critical": "red",
            "High":     "orange",
            "Moderate": "yellow",
            "Low":      "blue",
            "None":     "green",
        }.get(self.severity, "slate")

    @property
    def is_not_plant_error(self):
        return self.status == "failed" and self.error_message.startswith("NOT_A_PLANT:")
