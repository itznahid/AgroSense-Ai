from django.contrib import admin
from .models import UserProfile, Prediction

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'language', 'created_at')
    search_fields = ('user__username', 'user__email', 'phone')
    list_filter = ('language',)

@admin.register(Prediction)
class PredictionAdmin(admin.ModelAdmin):
    list_display = ('user', 'predicted_crop', 'created_at')
    search_fields = ('user__user__username', 'predicted_crop')
