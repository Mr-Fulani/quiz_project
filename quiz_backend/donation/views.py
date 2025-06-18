from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
import logging

from .forms import DonationForm
from .models import Donation

logger = logging.getLogger(__name__)


def donation_page(request):
    """Страница donation с формой оплаты"""
    success_message = None
    error_message = None
    
    if request.method == 'POST':
        form = DonationForm(request.POST)
        if form.is_valid():
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
                
            donation.save()
            
            # Здесь будет интеграция с Stripe
            # Пока просто сохраняем как pending
            success_message = _('Thank you for your donation! Your contribution helps us improve the platform.')
            
            # Очищаем форму после успешной отправки
            form = DonationForm()
            if request.user.is_authenticated:
                form.initial['email'] = request.user.email
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
        'title': _('Support Our Project'),
        'page_title': _('Donation'),
        'success_message': success_message,
        'error_message': error_message,
    }
    return render(request, 'donation/donation_page.html', context)


@csrf_exempt
@require_http_methods(["POST"])
def process_payment(request):
    """API endpoint для обработки платежей (будет использоваться с Stripe)"""
    try:
        data = json.loads(request.body)
        
        # Здесь будет логика интеграции с Stripe
        # Пока просто возвращаем успех
        
        return JsonResponse({
            'success': True,
            'message': _('Payment processed successfully')
        })
        
    except Exception as e:
        logger.error(f"Payment processing error: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': _('Payment processing failed')
        }, status=400)


 