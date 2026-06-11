from django import forms
from django.core.validators import RegexValidator

BD_PHONE_RE = RegexValidator(
    r'^\+?8801[3-9]\d{8}$|^01[3-9]\d{8}$',
    'Enter a valid Bangladesh mobile number (e.g. 01712345678).',
)

BD_DISTRICTS = [
    ('', '— Select District —'),
    ('Bagerhat', 'Bagerhat'), ('Bandarban', 'Bandarban'), ('Barguna', 'Barguna'),
    ('Barisal', 'Barisal'), ('Bhola', 'Bhola'), ('Bogra', 'Bogra'),
    ('Brahmanbaria', 'Brahmanbaria'), ('Chandpur', 'Chandpur'),
    ('Chapainawabganj', 'Chapainawabganj'), ('Chittagong', 'Chittagong'),
    ('Chuadanga', 'Chuadanga'), ('Comilla', 'Comilla'),
    ("Cox's Bazar", "Cox's Bazar"), ('Dhaka', 'Dhaka'), ('Dinajpur', 'Dinajpur'),
    ('Faridpur', 'Faridpur'), ('Feni', 'Feni'), ('Gaibandha', 'Gaibandha'),
    ('Gazipur', 'Gazipur'), ('Gopalganj', 'Gopalganj'), ('Habiganj', 'Habiganj'),
    ('Jamalpur', 'Jamalpur'), ('Jessore', 'Jessore'), ('Jhalokati', 'Jhalokati'),
    ('Jhenaidah', 'Jhenaidah'), ('Joypurhat', 'Joypurhat'),
    ('Khagrachari', 'Khagrachari'), ('Khulna', 'Khulna'), ('Kishoreganj', 'Kishoreganj'),
    ('Kurigram', 'Kurigram'), ('Kushtia', 'Kushtia'), ('Lakshmipur', 'Lakshmipur'),
    ('Lalmonirhat', 'Lalmonirhat'), ('Madaripur', 'Madaripur'), ('Magura', 'Magura'),
    ('Manikganj', 'Manikganj'), ('Meherpur', 'Meherpur'), ('Moulvibazar', 'Moulvibazar'),
    ('Munshiganj', 'Munshiganj'), ('Mymensingh', 'Mymensingh'), ('Naogaon', 'Naogaon'),
    ('Narail', 'Narail'), ('Narayanganj', 'Narayanganj'), ('Narsingdi', 'Narsingdi'),
    ('Natore', 'Natore'), ('Netrokona', 'Netrokona'), ('Nilphamari', 'Nilphamari'),
    ('Noakhali', 'Noakhali'), ('Pabna', 'Pabna'), ('Panchagarh', 'Panchagarh'),
    ('Patuakhali', 'Patuakhali'), ('Pirojpur', 'Pirojpur'), ('Rajbari', 'Rajbari'),
    ('Rajshahi', 'Rajshahi'), ('Rangamati', 'Rangamati'), ('Rangpur', 'Rangpur'),
    ('Satkhira', 'Satkhira'), ('Shariatpur', 'Shariatpur'), ('Sherpur', 'Sherpur'),
    ('Sirajganj', 'Sirajganj'), ('Sunamganj', 'Sunamganj'), ('Sylhet', 'Sylhet'),
    ('Tangail', 'Tangail'), ('Thakurgaon', 'Thakurgaon'),
]

_INPUT  = 'w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-[#10B981]/60 transition-colors'
_SELECT = 'w-full bg-[#0f172a] border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-[#10B981]/60 transition-colors cursor-pointer'
_AREA   = 'w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-[#10B981]/60 transition-colors resize-none'


class CheckoutForm(forms.Form):
    full_name = forms.CharField(
        max_length=150,
        label='Full Name',
        widget=forms.TextInput(attrs={'class': _INPUT, 'placeholder': 'Your full name'}),
    )
    phone = forms.CharField(
        max_length=16,
        label='Phone Number',
        validators=[BD_PHONE_RE],
        widget=forms.TextInput(attrs={'class': _INPUT, 'placeholder': '01712345678'}),
    )
    district = forms.ChoiceField(
        choices=BD_DISTRICTS,
        label='District',
        widget=forms.Select(attrs={'class': _SELECT}),
    )
    area = forms.CharField(
        max_length=150,
        label='Area / Upazila / Thana',
        widget=forms.TextInput(attrs={'class': _INPUT, 'placeholder': 'e.g. Mirpur-10'}),
    )
    full_address = forms.CharField(
        label='Full Address',
        widget=forms.Textarea(attrs={'class': _AREA, 'rows': 3,
                                     'placeholder': 'House/Road/Block details…'}),
    )
    notes = forms.CharField(
        required=False,
        label='Order Notes (optional)',
        widget=forms.Textarea(attrs={'class': _AREA, 'rows': 2,
                                     'placeholder': 'Any special instructions…'}),
    )
