from django import forms
from django.core.exceptions import ValidationError
from .models import CropDiseaseScan

# FIX: removed "bmp" — Gemini Vision does not accept image/bmp.
# The original code allowed BMP uploads but _mime_from_name() had no BMP
# branch, so it silently sent the file to Gemini as "image/jpeg", which
# caused silent mis-classification or API errors.
ALLOWED_EXTENSIONS = ["jpg", "jpeg", "png", "webp"]
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_UPLOAD_SIZE = 10 * 1024 * 1024


class CropDiseaseForm(forms.ModelForm):
    class Meta:
        model = CropDiseaseScan
        fields = ["image"]
        widgets = {
            "image": forms.ClearableFileInput(attrs={
                "class": "form-control",
                "accept": "image/jpeg,image/png,image/webp",
            }),
        }
        labels = {
            "image": "Upload Crop/Plant Leaf Image",
        }
        help_texts = {
            "image": "Accepted formats: JPG, PNG, WebP. Max 10 MB.",
        }

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if image:
            ext = image.name.rsplit(".", 1)[-1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                raise ValidationError(
                    f"Unsupported file type '.{ext}'. "
                    f"Please upload one of: {', '.join(ALLOWED_EXTENSIONS).upper()}."
                )
            content_type = getattr(image, "content_type", "")
            if content_type and content_type not in ALLOWED_CONTENT_TYPES:
                raise ValidationError("Unsupported image content type.")
            if image.size > MAX_UPLOAD_SIZE:
                raise ValidationError(
                    f"File size ({image.size / 1024 / 1024:.1f} MB) exceeds the 10 MB limit."
                )
        return image
