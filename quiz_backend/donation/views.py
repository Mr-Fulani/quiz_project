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
from .utils import send_donation_thank_you_email

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
    # Теперь обработка платежей происходит через JavaScript + Stripe API
    # Этот view только отображает форму
    
    form = DonationForm()
    # Если пользователь авторизован, предзаполняем email
    if request.user.is_authenticated:
        form.initial['email'] = request.user.email
    
    context = {
        'form': form,
        'title': _('Support'),
        'page_title': _('Donation'),
        'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY,
    }
    return render(request, 'donation/donation_page.html', context)


@csrf_exempt
@require_http_methods(["POST"])
def create_payment_intent(request):
    """Создание Payment Intent для Stripe"""
    logger.info(f"Create payment intent request received: {request.body}")
    try:
        data = json.loads(request.body)
        amount = data.get('amount')
        currency = data.get('currency', 'usd')
        email = data.get('email', '')
        name = data.get('name', '')
        logger.info(f"Payment intent data: amount={amount}, currency={currency}, email={email}, name={name}")
        
        # Валидация данных
        if not amount or float(amount) < 1:
            return JsonResponse({
                'success': False,
                'message': _('Invalid amount. Minimum amount is $1.00')
            }, status=400)
        
        if not name or not name.strip():
            return JsonResponse({
                'success': False,
                'message': _('Name is required')
            }, status=400)
        
        # Проверка поддерживаемых валют
        supported_currencies = ['usd', 'eur', 'rub']
        if currency not in supported_currencies:
            return JsonResponse({
                'success': False,
                'message': _('Unsupported currency')
            }, status=400)
        
        # Конвертируем в центы для Stripe (для RUB не нужно умножать на 100)
        if currency == 'rub':
            amount_cents = int(float(amount))
        else:
            amount_cents = int(float(amount) * 100)
        
        # Создаем Payment Intent
        intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency=currency,
            metadata={
                'user_email': email,
                'user_name': name,
            },
            automatic_payment_methods={
                'enabled': True,
            }
        )
        
        logger.info(f"Payment intent created: {intent.id} for {amount} {currency}")
        
        return JsonResponse({
            'success': True,
            'client_secret': intent.client_secret,
            'payment_intent_id': intent.id
        })
        
    except stripe.error.CardError as e:
        logger.error(f"Stripe card error: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': _('Card error: ') + str(e.user_message)
        }, status=400)
        
    except stripe.error.RateLimitError as e:
        logger.error(f"Stripe rate limit error: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': _('Too many requests. Please try again later.')
        }, status=429)
        
    except stripe.error.InvalidRequestError as e:
        logger.error(f"Stripe invalid request error: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': _('Invalid request parameters')
        }, status=400)
        
    except stripe.error.AuthenticationError as e:
        logger.error(f"Stripe authentication error: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': _('Authentication error. Please contact support.')
        }, status=500)
        
    except stripe.error.APIConnectionError as e:
        logger.error(f"Stripe API connection error: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': _('Network error. Please check your connection.')
        }, status=500)
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': _('Payment service error. Please try again.')
        }, status=500)
        
    except json.JSONDecodeError:
        logger.error("Invalid JSON in request body")
        return JsonResponse({
            'success': False,
            'message': _('Invalid request format')
        }, status=400)
        
    except ValueError as e:
        logger.error(f"Value error: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': _('Invalid amount format')
        }, status=400)
        
    except Exception as e:
        logger.error(f"Unexpected error creating payment intent: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': _('An unexpected error occurred. Please try again.')
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def create_payment_method(request):
    """Создание payment method на сервере"""
    try:
        data = json.loads(request.body)
        
        # Получаем данные карты
        card_number = data.get('card_number')
        exp_month = data.get('exp_month')
        exp_year = data.get('exp_year')
        cvc = data.get('cvc')
        name = data.get('name', '')
        email = data.get('email', '')
        
        # Валидация
        if not all([card_number, exp_month, exp_year, cvc]):
            return JsonResponse({
                'success': False,
                'message': _('All card fields are required')
            }, status=400)
        
        # Создаем payment method в Stripe
        payment_method = stripe.PaymentMethod.create(
            type='card',
            card={
                'number': card_number,
                'exp_month': exp_month,
                'exp_year': exp_year,
                'cvc': cvc,
            },
            billing_details={
                'name': name,
                'email': email,
            }
        )
        
        return JsonResponse({
            'success': True,
            'payment_method_id': payment_method.id
        })
        
    except stripe.error.CardError as e:
        logger.error(f"Stripe card error: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': str(e.user_message)
        }, status=400)
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': _('Payment method creation error')
        }, status=400)
        
    except Exception as e:
        logger.error(f"Payment method creation error: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': _('An error occurred')
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def confirm_payment(request):
    """Подтверждение успешного платежа"""
    logger.info(f"Confirm payment request received: {request.body}")
    try:
        data = json.loads(request.body)
        payment_intent_id = data.get('payment_intent_id')
        logger.info(f"Payment intent ID: {payment_intent_id}")
        
        if not payment_intent_id:
            return JsonResponse({
                'success': False,
                'message': _('Payment intent ID required')
            }, status=400)
        
        # Получаем Payment Intent из Stripe
        intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        
        if intent.status == 'succeeded':
            # Конвертируем сумму в зависимости от валюты
            if intent.currency == 'rub':
                amount = intent.amount  # RUB не конвертируем
            else:
                amount = intent.amount / 100  # USD/EUR конвертируем из центов
            
            # Создаем или обновляем donation
            donation, created = Donation.objects.get_or_create(
                stripe_payment_intent_id=payment_intent_id,
                defaults={
                    'amount': amount,
                    'currency': intent.currency,
                    'status': 'completed',
                    'name': intent.metadata.get('user_name', 'Anonymous'),
                    'email': intent.metadata.get('user_email', ''),
                    'payment_method': 'stripe'
                }
            )
            
            if not created:
                donation.status = 'completed'
                donation.save()
            
            # Отправляем email благодарности
            try:
                send_donation_thank_you_email(donation)
                logger.info(f"Thank you email sent for donation {donation.id}")
            except Exception as e:
                logger.error(f"Failed to send thank you email for donation {donation.id}: {str(e)}")
            
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


@csrf_exempt
@require_http_methods(["POST"])
def stripe_webhook(request):
    """Webhook для обработки событий Stripe"""
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET
    
    if not endpoint_secret:
        logger.warning("Stripe webhook secret not configured")
        return JsonResponse({'status': 'error', 'message': 'Webhook not configured'}, status=400)
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError:
        logger.error("Invalid payload in webhook")
        return JsonResponse({'status': 'error', 'message': 'Invalid payload'}, status=400)
    except stripe.error.SignatureVerificationError:
        logger.error("Invalid signature in webhook")
        return JsonResponse({'status': 'error', 'message': 'Invalid signature'}, status=400)
    
    # Обработка различных типов событий
    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        logger.info(f"Webhook: Payment succeeded for {payment_intent['id']}")
        
        try:
            # Конвертируем сумму в зависимости от валюты
            if payment_intent['currency'] == 'rub':
                amount = payment_intent['amount']
            else:
                amount = payment_intent['amount'] / 100
            
            # Обновляем или создаем donation
            donation, created = Donation.objects.get_or_create(
                stripe_payment_intent_id=payment_intent['id'],
                defaults={
                    'amount': amount,
                    'currency': payment_intent['currency'],
                    'status': 'completed',
                    'name': payment_intent['metadata'].get('user_name', 'Anonymous'),
                    'email': payment_intent['metadata'].get('user_email', ''),
                    'payment_method': 'stripe'
                }
            )
            
            if not created and donation.status != 'completed':
                donation.status = 'completed'
                donation.save()
                logger.info(f"Donation {donation.id} updated to completed via webhook")
                
                # Отправляем email благодарности
                try:
                    send_donation_thank_you_email(donation)
                    logger.info(f"Thank you email sent for donation {donation.id} via webhook")
                except Exception as e:
                    logger.error(f"Failed to send thank you email for donation {donation.id} via webhook: {str(e)}")
            
        except Exception as e:
            logger.error(f"Error processing webhook payment_intent.succeeded: {str(e)}")
            
    elif event['type'] == 'payment_intent.payment_failed':
        payment_intent = event['data']['object']
        logger.info(f"Webhook: Payment failed for {payment_intent['id']}")
        
        try:
            donation = Donation.objects.filter(
                stripe_payment_intent_id=payment_intent['id']
            ).first()
            
            if donation and donation.status != 'failed':
                donation.status = 'failed'
                donation.save()
                logger.info(f"Donation {donation.id} marked as failed via webhook")
                
        except Exception as e:
            logger.error(f"Error processing webhook payment_intent.payment_failed: {str(e)}")
            
    elif event['type'] == 'payment_intent.canceled':
        payment_intent = event['data']['object']
        logger.info(f"Webhook: Payment canceled for {payment_intent['id']}")
        
        try:
            donation = Donation.objects.filter(
                stripe_payment_intent_id=payment_intent['id']
            ).first()
            
            if donation and donation.status not in ['completed', 'cancelled']:
                donation.status = 'cancelled'
                donation.save()
                logger.info(f"Donation {donation.id} marked as cancelled via webhook")
                
        except Exception as e:
            logger.error(f"Error processing webhook payment_intent.canceled: {str(e)}")
    
    else:
        logger.info(f"Webhook: Unhandled event type {event['type']}")
    
    return JsonResponse({'status': 'success'})


@require_http_methods(["GET"])
def get_stripe_publishable_key(request):
    """Получение публичного ключа Stripe для фронтенда"""
    try:
        publishable_key = settings.STRIPE_PUBLISHABLE_KEY
        if not publishable_key or publishable_key.startswith('pk_test_51234'):
            logger.warning("Stripe publishable key not configured properly")
            return JsonResponse({
                'success': False,
                'message': 'Stripe not configured'
            }, status=400)
        
        return JsonResponse({
            'success': True,
            'publishable_key': publishable_key
        })
        
    except Exception as e:
        logger.error(f"Error getting Stripe publishable key: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': 'Error getting Stripe key'
        }, status=500)
 