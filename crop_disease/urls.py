from django.urls import path
from . import views

app_name = "crop_disease"

urlpatterns = [
    # Web UI
    path("",               views.scan_upload,  name="scan_upload"),
    path("result/<int:pk>/", views.scan_result, name="scan_result"),
    path("history/",       views.scan_history, name="scan_history"),
    path("detail/<int:pk>/", views.scan_detail, name="scan_detail"),

    # REST API
    path("api/predict/",   views.api_predict,  name="api_predict"),
]
