import csv
from django.http import HttpResponse
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Donation


def export_donations_csv(request, queryset=None):
    """Экспорт донатов в CSV файл"""
    if queryset is None:
        queryset = Donation.objects.all()
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="donations_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    response.write('\ufeff')  # UTF-8 BOM для правильного отображения в Excel
    
    writer = csv.writer(response)
    writer.writerow([
        'ID', 'Имя', 'Email', 'Сумма', 'Валюта', 'Статус', 
        'Способ оплаты', 'Stripe ID', 'Дата создания', 'Дата обновления'
    ])
    
    for donation in queryset:
        writer.writerow([
            donation.id,
            donation.name,
            donation.email,
            donation.amount,
            donation.currency,
            donation.get_status_display(),
            donation.payment_method or '',
            donation.stripe_payment_intent_id or '',
            donation.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            donation.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
        ])
    
    return response


def get_donation_statistics(days=30):
    """Получить статистику донатов за определенный период по валютам"""
    end_date = timezone.now()
    start_date = end_date - timedelta(days=days)
    
    # Общая статистика
    donations = Donation.objects.filter(created_at__gte=start_date)
    stats = {
        'period_days': days,
        'total_donations': donations.count(),
        'completed_donations': donations.filter(status='completed').count(),
        'pending_donations': donations.filter(status='pending').count(),
        'failed_donations': donations.filter(status='failed').count(),
        'currency_stats': {}
    }
    
    # Статистика по валютам
    for currency_code, currency_name in Donation.CURRENCY_CHOICES:
        currency_donations = donations.filter(currency=currency_code)
        currency_completed = currency_donations.filter(status='completed')
        
        currency_stats = {
            'name': currency_name,
            'total_donations': currency_donations.count(),
            'completed_donations': currency_completed.count(),
            'pending_donations': currency_donations.filter(status='pending').count(),
            'failed_donations': currency_donations.filter(status='failed').count(),
            'total_amount': sum(d.amount for d in currency_completed),
        }
        
        stats['currency_stats'][currency_code] = currency_stats
    
    return stats


def get_top_donors(limit=10, currency=None):
    """Получить топ донатеров по валютам"""
    from django.db.models import Sum, Count
    
    if currency:
        # Топ донатеров по конкретной валюте
        return Donation.objects.filter(
            status='completed',
            currency=currency
        ).values(
            'name', 'email', 'currency'
        ).annotate(
            total_amount=Sum('amount'),
            donation_count=Count('id')
        ).order_by('-total_amount')[:limit]
    else:
        # Топ донатеров по всем валютам с группировкой
        result = {}
        for currency_code, currency_name in Donation.CURRENCY_CHOICES:
            result[currency_code] = {
                'name': currency_name,
                'donors': Donation.objects.filter(
                    status='completed',
                    currency=currency_code
                ).values(
                    'name', 'email'
                ).annotate(
                    total_amount=Sum('amount'),
                    donation_count=Count('id')
                ).order_by('-total_amount')[:limit]
            }
        return result


def detect_user_language(donation):
    """Определяет язык пользователя для отправки email"""
    import re
    
    # Приоритет 1: Проверяем язык связанного пользователя (CustomUser)
    if hasattr(donation, 'user') and donation.user and donation.user.language:
        user_lang = donation.user.language.lower()
        if user_lang in ['ru', 'russian', 'русский']:
            return 'ru'
        elif user_lang in ['en', 'english', 'английский']:
            return 'en'
        # Если другой язык - используем русский как fallback
        return 'en'
    
    # Приоритет 2: Поиск пользователя по email
    if donation.email:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            user = User.objects.get(email=donation.email)
            if user.language:
                user_lang = user.language.lower()
                if user_lang in ['ru', 'russian', 'русский']:
                    return 'ru'
                elif user_lang in ['en', 'english', 'английский']:
                    return 'en'
                return 'en'
        except User.DoesNotExist:
            pass
    
    # Приоритет 3: Проверяем валюту - если рубли, то скорее всего русский пользователь
    if donation.currency == 'rub':
        return 'ru'
    
    # Приоритет 4: Проверяем по имени - если содержит кириллицу, то русский
    if donation.name:
        if re.search(r'[а-яёА-ЯЁ]', donation.name):
            return 'ru'
    
    # Приоритет 5: Проверяем по email домену
    if donation.email:
        email_lower = donation.email.lower()
        russian_domains = ['.ru', '.рф', '.su', '.by', '.kz', '.ua', 'mail.ru', 'yandex.ru', 'rambler.ru', 'bk.ru']
        for domain in russian_domains:
            if domain in email_lower:
                return 'ru'
    
    # По умолчанию английский (основной язык сайта)
    return 'en'


def send_donation_thank_you_email(donation):
    """Отправить благодарственное письмо за донат с поддержкой локализации"""
    from django.core.mail import EmailMultiAlternatives
    from django.template.loader import render_to_string
    from django.conf import settings
    import logging

    logger = logging.getLogger(__name__)

    if donation.status != 'completed' or not donation.email:
        logger.info(f"Skipping email for donation {donation.id}: status={donation.status}, email={donation.email}")
        return False
    
    # Определяем язык пользователя
    language = detect_user_language(donation)
    
    # Устанавливаем тему письма в зависимости от языка
    if language == 'ru':
        subject = f'🎉 Спасибо за ваш донат! - Quiz Project'
    else:
        subject = f'🎉 Thank you for your donation! - Quiz Project'
    
    # Контекст для шаблонов
    context = {'donation': donation}
    
    # Генерируем текстовую и HTML версии в зависимости от языка
    text_template = f'donation/thank_you_email_{language}.txt'
    html_template = f'donation/thank_you_email_{language}.html'
    
    try:
        text_content = render_to_string(text_template, context)
        html_content = render_to_string(html_template, context)
        
        # Создаем письмо с поддержкой HTML и текста
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[donation.email]
        )
        
        # Прикрепляем HTML версию
        email.attach_alternative(html_content, "text/html")
        
        # Отправляем
        email.send()
        logger.info(f"Email успешно отправлен на язык {language} для {donation.email} (донат {donation.id})")
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки email для доната {donation.id} на языке {language}: {e}. Пробуем fallback.")
        # Fallback на русский язык в случае ошибки
        try:
            text_content = render_to_string('donation/thank_you_email_ru.txt', context)
            html_content = render_to_string('donation/thank_you_email_ru.html', context)
            
            email = EmailMultiAlternatives(
                subject=f'🎉 Спасибо за ваш донат! - Quiz Project',
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[donation.email]
            )
            
            email.attach_alternative(html_content, "text/html")
            email.send()
            logger.info(f"Email успешно отправлен (fallback русский) для {donation.email} (донат {donation.id})")
            return True
        except Exception as fallback_e:
            logger.error(f"Ошибка отправки fallback email для доната {donation.id}: {fallback_e}")
            return False
 