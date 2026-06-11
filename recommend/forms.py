from django import forms


# ── Crop Prediction ───────────────────────────────────────────────────────────

class CropPredictionForm(forms.Form):
    # Soil macronutrients (kg/ha)
    nitrogen = forms.FloatField(
        label='Nitrogen (N)',
        min_value=0, max_value=140,
        widget=forms.NumberInput(attrs={'placeholder': '0 – 140', 'step': '0.1'}),
        help_text='kg/ha',
    )
    phosphorus = forms.FloatField(
        label='Phosphorus (P)',
        min_value=0, max_value=145,
        widget=forms.NumberInput(attrs={'placeholder': '0 – 145', 'step': '0.1'}),
        help_text='kg/ha',
    )
    potassium = forms.FloatField(
        label='Potassium (K)',
        min_value=0, max_value=205,
        widget=forms.NumberInput(attrs={'placeholder': '0 – 205', 'step': '0.1'}),
        help_text='kg/ha',
    )
    # Climate
    temperature = forms.FloatField(
        label='Temperature',
        min_value=0, max_value=51,
        widget=forms.NumberInput(attrs={'placeholder': '0 – 51', 'step': '0.01'}),
        help_text='°C',
    )
    humidity = forms.FloatField(
        label='Humidity',
        min_value=0, max_value=100,
        widget=forms.NumberInput(attrs={'placeholder': '0 – 100', 'step': '0.01'}),
        help_text='%',
    )
    # Soil chemistry
    ph = forms.FloatField(
        label='Soil pH',
        min_value=0, max_value=14,
        widget=forms.NumberInput(attrs={'placeholder': '0 – 14', 'step': '0.01'}),
        help_text='0 = acidic, 14 = alkaline',
    )
    rainfall = forms.FloatField(
        label='Rainfall',
        min_value=0, max_value=300,
        widget=forms.NumberInput(attrs={'placeholder': '0 – 300', 'step': '0.1'}),
        help_text='mm',
    )

    def get_feature_vector(self):
        """Return inputs in the exact order the model was trained on: N P K temp humidity ph rainfall."""
        cd = self.cleaned_data
        return [
            cd['nitrogen'],
            cd['phosphorus'],
            cd['potassium'],
            cd['temperature'],
            cd['humidity'],
            cd['ph'],
            cd['rainfall'],
        ]