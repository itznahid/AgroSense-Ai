from django.db import models
from django.contrib.auth.models import User


LANGUAGE_CHOICES = [
    ('en', 'English'),
    ('bn', 'বাংলা (Bengali)'),
    ('hi', 'हिन्दी (Hindi)'),
    ('ur', 'اردو (Urdu)'),
    ('ar', 'العربية (Arabic)'),
    ('fr', 'Français (French)'),
    ('es', 'Español (Spanish)'),
    ('pt', 'Português (Portuguese)'),
    ('sw', 'Kiswahili (Swahili)'),
    ('zh', '中文 (Chinese)'),
]


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UserProfile(BaseModel):
    user     = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone    = models.CharField(max_length=25)
    language = models.CharField(max_length=10, choices=LANGUAGE_CHOICES, default='en')
    primary_crop = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return self.user.get_full_name() or self.user.username


class Prediction(BaseModel):
    user         = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    Nitrogen     = models.FloatField()
    Phosphorus   = models.FloatField()
    Potassium    = models.FloatField()
    Temperature  = models.FloatField()
    Humidity     = models.FloatField()
    pH           = models.FloatField()
    Rainfall     = models.FloatField()
    predicted_crop = models.CharField(max_length=100)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user} -> {self.predicted_crop}"
