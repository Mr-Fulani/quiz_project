from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import json
import logging
import stripe

from .forms import DonationForm
from .models import Donation

logger = logging.getLogger(__name__)

# Настройка Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

# Проверяем что ключи настроены
if not settings.STRIPE_SECRET_KEY or settings.STRIPE_SECRET_KEY.startswith('sk_test_51234'):
    logger.warning("Stripe secret key not configured properly!")
if not settings.STRIPE_PUBLISHABLE_KEY or settings.STRIPE_PUBLISHABLE_KEY.startswith('pk_test_51234'):
    logger.warning("Stripe publishable key not configured properly!")


def donation_page(request):
    """Страница donation с формой оплаты"""
    success_message = None
    error_message = None
    
    if request.method == 'POST':
        form = DonationForm(request.POST)
        if form.is_valid():
            try:
                donation = form.save(commit=False)
                if request.user.is_authenticated:
                    donation.user = request.user
                
                # Получаем имя из поля карты
                card_name = request.POST.get('card_name', '')
                if card_name:
                    donation.name = card_name
                elif request.user.is_authenticated:
                    donation.name = f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username
                else:
                    donation.name = "Anonymous"
                
                # Создаем Payment Intent в Stripe
                intent = stripe.PaymentIntent.create(
                    amount=int(donation.amount * 100),  # Stripe принимает центы
                    currency='usd',
                    metadata={
                        'donation_id': str(donation.id) if donation.id else 'new',
                        'user_email': donation.email,
                        'user_name': donation.name
                    }
                )
                
                # Сохраняем donation с payment_intent_id
                donation.stripe_payment_intent_id = intent.id
                donation.status = 'pending'
                donation.save()
                
                success_message = _('Thank you for your donation! Your contribution helps us improve the platform.')
                
                # Очищаем форму после успешной отправки
                form = DonationForm()
                if request.user.is_authenticated:
                    form.initial['email'] = request.user.email
                    
            except stripe.error.StripeError as e:
                logger.error(f"Stripe error: {str(e)}")
                error_message = _('Payment processing error. Please try again.')
            except Exception as e:
                logger.error(f"Donation processing error: {str(e)}")
                error_message = _('An error occurred. Please try again.')
        else:
            # Ошибки валидации
            error_message = _('Please correct the errors below and try again.')
    else:
        form = DonationForm()
        # Если пользователь авторизован, предзаполняем email
        if request.user.is_authenticated:
            form.initial['email'] = request.user.email
    
    context = {
        'form': form,
        'title': _('Support'),
        'page_title': _('Donation'),
        'success_message': success_message,
        'error_message': error_message,
        'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY,
    }
    return render(request, 'donation/donation_page.html', context)


@csrf_exempt
@require_http_methods(["POST"])
def create_payment_intent(request):
    """Создание Payment Intent для Stripe"""
    try:
        data = json.loads(request.body)
        amount = data.get('amount')
        email = data.get('email')
        name = data.get('name')
        
        if not amount or float(amount) <= 0:
            return JsonResponse({
                'success': False,
                'message': _('Invalid amount')
            }, status=400)
        
        # Создаем Payment Intent
        intent = stripe.PaymentIntent.create(
            amount=int(float(amount) * 100),  # Stripe принимает центы
            currency='usd',
            metadata={
                'user_email': email or '',
                'user_name': name or ''
            }
        )
        
        return JsonResponse({
            'success': True,
            'client_secret': intent.client_secret,
            'payment_intent_id': intent.id
        })
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': _('Payment processing error')
        }, status=400)
    except Exception as e:
        logger.error(f"Payment intent creation error: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': _('An error occurred')
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def confirm_payment(request):
    """Подтверждение успешного платежа"""
    try:
        data = json.loads(request.body)
        payment_intent_id = data.get('payment_intent_id')
        
        if not payment_intent_id:
            return JsonResponse({
                'success': False,
                'message': _('Payment intent ID required')
            }, status=400)
        
        # Получаем Payment Intent из Stripe
        intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        
        if intent.status == 'succeeded':
            # Создаем или обновляем donation
            donation, created = Donation.objects.get_or_create(
                stripe_payment_intent_id=payment_intent_id,
                defaults={
                    'amount': intent.amount / 100,  # Конвертируем из центов
                    'currency': intent.currency.upper(),
                    'status': 'completed',
                    'name': intent.metadata.get('user_name', 'Anonymous'),
                    'email': intent.metadata.get('user_email', ''),
                    'payment_method': 'stripe'
                }
            )
            
            if not created:
                donation.status = 'completed'
                donation.save()
            
            return JsonResponse({
                'success': True,
                'message': _('Payment confirmed successfully')
            })
        else:
            return JsonResponse({
                'success': False,
                'message': _('Payment not completed')
            }, status=400)
            
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': _('Payment confirmation error')
        }, status=400)
    except Exception as e:
        logger.error(f"Payment confirmation error: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': _('An error occurred')
        }, status=500)


def test_stripe(request):
    """Тестовая страница для проверки Stripe"""
    return render(request, 'donation/test_stripe.html', {
        'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY
    })


 