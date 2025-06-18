from django import forms
from django.utils.translation import gettext_lazy as _
from .models import Donation


class DonationForm(forms.ModelForm):
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=1.00,
        widget=forms.NumberInput(attrs={
            'class': 'custom-amount',
            'placeholder': _('Enter amount'),
            'step': '0.01',
            'min': '1.00'
        }),
        label=_('Amount ($)')
    )
    
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'field-input',
            'placeholder': _('Enter your email (optional)')
        }),
        label=_('Email (optional)')
    )
    
    class Meta:
        model = Donation
        fields = ['email', 'amount']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Добавляем CSS классы для всех полей
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control' 