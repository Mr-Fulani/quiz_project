from django.db import models
from django.contrib.auth import get_user_model
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class Donation(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('completed', _('Completed')),
        ('failed', _('Failed')),
        ('cancelled', _('Cancelled')),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        verbose_name=_('User')
    )
    name = models.CharField(
        max_length=100,
        verbose_name=_('Name')
    )
    email = models.EmailField(
        verbose_name=_('Email'),
        null=True,
        blank=True
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_('Amount')
    )
    CURRENCY_CHOICES = [
        ('usd', 'USD ($)'),
        ('eur', 'EUR (€)'),
        ('rub', 'RUB (₽)'),
    ]
    
    currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default='usd',
        verbose_name=_('Currency')
    )
    payment_method = models.CharField(
        max_length=50,
        verbose_name=_('Payment Method'),
        null=True,
        blank=True
    )
    status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='pending',
        verbose_name=_('Status')
    )
    stripe_payment_intent_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name=_('Stripe Payment Intent ID')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created At')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Updated At')
    )
    
    class Meta:
        verbose_name = _('Donation')
        verbose_name_plural = _('Donations')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - ${self.amount} ({self.status})" 