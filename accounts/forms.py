from django import forms
from django.contrib.auth.models import User

from marketplace.models import Product, Category
from .models import MerchantProfile


# ── Shared crop choices ───────────────────────────────────────────────────────

CROP_CHOICES = [
    ('rice', 'Rice 🌾'),           ('maize', 'Maize 🌽'),
    ('chickpea', 'Chickpea 🫘'),   ('kidneybeans', 'Kidney Beans 🫘'),
    ('pigeonpeas', 'Pigeon Peas 🌿'), ('mothbeans', 'Moth Beans 🌿'),
    ('mungbean', 'Mung Bean 🫘'),  ('blackgram', 'Black Gram 🫘'),
    ('lentil', 'Lentil 🫘'),       ('pomegranate', 'Pomegranate 🍎'),
    ('banana', 'Banana 🍌'),       ('mango', 'Mango 🥭'),
    ('grapes', 'Grapes 🍇'),       ('watermelon', 'Watermelon 🍉'),
    ('muskmelon', 'Muskmelon 🍈'), ('apple', 'Apple 🍎'),
    ('orange', 'Orange 🍊'),       ('papaya', 'Papaya 🍑'),
    ('coconut', 'Coconut 🥥'),     ('cotton', 'Cotton 🌸'),
    ('jute', 'Jute 🌿'),           ('coffee', 'Coffee ☕'),
]

SHOP_ICON_CHOICES = [
    ('🏪', '🏪 General Store'),
    ('🌱', '🌱 Seeds & Crops'),
    ('🧪', '🧪 Fertilisers'),
    ('🚜', '🚜 Equipment'),
    ('💊', '💊 Pesticides'),
    ('🌾', '🌾 Grain & Cereals'),
]


# ── Base registration form ────────────────────────────────────────────────────

class _BaseRegisterForm(forms.Form):
    first_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'placeholder': 'First name', 'autocomplete': 'given-name'}),
    )
    last_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'placeholder': 'Last name', 'autocomplete': 'family-name'}),
    )
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'placeholder': 'Choose a username', 'autocomplete': 'username'}),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'placeholder': 'you@example.com', 'autocomplete': 'email'}),
    )
    phone = forms.CharField(
        max_length=25, required=False,
        widget=forms.TextInput(attrs={'placeholder': '+880 1XXX-XXXXXX', 'type': 'tel'}),
    )
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'placeholder': 'Create a password', 'autocomplete': 'new-password'}),
    )
    password2 = forms.CharField(
        label='Confirm password',
        widget=forms.PasswordInput(attrs={'placeholder': 'Repeat your password', 'autocomplete': 'new-password'}),
    )

    def clean_username(self):
        u = self.cleaned_data['username'].strip()
        if User.objects.filter(username__iexact=u).exists():
            raise forms.ValidationError('That username is already taken.')
        return u

    def clean_email(self):
        e = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=e).exists():
            raise forms.ValidationError('An account with that email already exists.')
        return e

    def clean(self):
        cd = super().clean()
        p1, p2 = cd.get('password1'), cd.get('password2')
        if p1 and p2 and p1 != p2:
            self.add_error('password2', 'Passwords do not match.')
        if p1 and len(p1) < 8:
            self.add_error('password1', 'Password must be at least 8 characters.')
        return cd


# ── User registration ─────────────────────────────────────────────────────────

class UserRegisterForm(_BaseRegisterForm):
    """Standard user registration – no shop fields."""

    def save(self):
        user = User.objects.create_user(
            username=self.cleaned_data["username"],
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password1"],
            first_name=self.cleaned_data["first_name"],
            last_name=self.cleaned_data["last_name"],
        )
        return user


# ── Merchant registration ─────────────────────────────────────────────────────

class MerchantRegisterForm(_BaseRegisterForm):
    """Merchant registration – includes shop fields."""

    # FIX: shop fields were missing; view accessed cleaned_data['shop_name'] etc. causing KeyError
    shop_name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'placeholder': 'Your shop name'}),
    )
    shop_icon = forms.ChoiceField(
        choices=SHOP_ICON_CHOICES,
        required=False,
        initial='🏪',
        widget=forms.Select(attrs={'class': 'auth-input'}),
    )
    shop_description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Briefly describe what you sell…'}),
    )

    def save(self):
        user = User.objects.create_user(
            username=self.cleaned_data["username"],
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password1"],
            first_name=self.cleaned_data["first_name"],
            last_name=self.cleaned_data["last_name"],
        )
        return user


# ── Merchant product form ─────────────────────────────────────────────────────

class MerchantProductForm(forms.ModelForm):
    suitable_crops = forms.MultipleChoiceField(
        choices=CROP_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text='Select the crops this product is recommended for.',
    )

    class Meta:
        model  = Product
        fields = [
            'name', 'category', 'description',
            'price', 'original_price', 'unit',
            'icon', 'image',
            'stock', 'badge',
            'suitable_crops', 'is_active',
        ]
        widgets = {
            'description':    forms.Textarea(attrs={'rows': 3, 'placeholder': 'Product description…'}),
            'name':           forms.TextInput(attrs={'placeholder': 'Product name'}),
            'price':          forms.NumberInput(attrs={'placeholder': '0.00', 'step': '0.01'}),
            'original_price': forms.NumberInput(attrs={'placeholder': '0.00 (optional)', 'step': '0.01'}),
            'unit':           forms.TextInput(attrs={'placeholder': 'e.g. per kg, per litre'}),
            'icon':           forms.TextInput(attrs={'placeholder': '🌱', 'maxlength': '10'}),
            'stock':          forms.NumberInput(attrs={'placeholder': '100'}),
        }

    def clean_suitable_crops(self):
        return list(self.cleaned_data.get('suitable_crops', []))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.suitable_crops:
            self.fields['suitable_crops'].initial = self.instance.suitable_crops


# ── Shop edit form ────────────────────────────────────────────────────────────

class ShopEditForm(forms.ModelForm):
    """Allows a merchant to update their shop profile, including logo upload."""

    shop_icon = forms.ChoiceField(
        choices=SHOP_ICON_CHOICES,
        required=False,
        initial='🏪',
        widget=forms.Select(attrs={'class': 'auth-input'}),
    )

    class Meta:
        model  = MerchantProfile
        fields = ['shop_name', 'shop_description', 'shop_icon', 'logo']
        widgets = {
            'shop_name':        forms.TextInput(attrs={'placeholder': 'Your shop name'}),
            'shop_description': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Describe your shop…'}),
        }


# ── User profile form ─────────────────────────────────────────────────────────

class UserProfileForm(forms.ModelForm):
    """Allows a regular user to update their Django User record."""
    phone = forms.CharField(
        max_length=25, required=False,
        widget=forms.TextInput(attrs={'placeholder': '+880 1XXX-XXXXXX', 'type': 'tel'}),
    )

    class Meta:
        model  = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'placeholder': 'First name'}),
            'last_name':  forms.TextInput(attrs={'placeholder': 'Last name'}),
            'email':      forms.EmailInput(attrs={'placeholder': 'you@example.com'}),
        }

    def clean_email(self):
        e = self.cleaned_data['email'].strip().lower()
        qs = User.objects.filter(email__iexact=e).exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('That email is already in use by another account.')
        return e


# ── Checkout form ─────────────────────────────────────────────────────────────

class CheckoutForm(forms.Form):
    delivery_address = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': 'House/Flat, Road, Area, City, District…',
        }),
    )
    phone = forms.CharField(
        max_length=25,
        widget=forms.TextInput(attrs={'placeholder': '+880 1XXX-XXXXXX', 'type': 'tel'}),
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'placeholder': 'Any special delivery instructions? (optional)'}),
    )
