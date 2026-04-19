"""
Сигналы для модели Donation.
Отправляют уведомления админам о новых донатах из Mini App.
"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from django.conf import settings

from .models import Donation

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Donation)
def notify_admins_about_donation(sender, instance, created, **kwargs):
    """
    Отправляет уведомление админам о новом донате из Mini App.
    
    Уведомление отправляется только если:
    - Источник доната - 'mini_app'
    - Статус - 'completed'
    - update_fields не содержит только updated_at (чтобы избежать дублей при автоматических обновлениях)
    
    Примечание: Уведомление может быть отправлено несколько раз если donation 
    обновляется несколько раз со статусом 'completed'. Это приемлемо для простоты реализации.
    """
    # Проверяем, нужно ли отправлять уведомление
    if instance.source != 'mini_app' or instance.status != 'completed':
        return
    
    # Проверяем update_fields, чтобы не отправлять при автоматических обновлениях
    update_fields = kwargs.get('update_fields')
    if update_fields is not None and update_fields == {'updated_at'}:
        return
    
    # Отправляем уведомление админам
    try:
        from accounts.utils_folder.telegram_notifications import notify_all_admins
        
        # Формируем информацию о донате
        donor_name = instance.name or "Аноним"
        
        # Пытаемся получить telegram_id
        telegram_id = None
        if instance.user:
            # Если есть связь с пользователем, пытаемся получить telegram_id
            if hasattr(instance.user, 'telegram_id'):
                telegram_id = instance.user.telegram_id
            elif hasattr(instance.user, 'miniappuser'):
                telegram_id = instance.user.miniappuser.telegram_id
        
        # Проверяем в payment metadata (для Stripe)
        if not telegram_id and instance.stripe_payment_intent_id:
            # Telegram ID может быть в метаданных платежа
            # Но мы не можем получить его без запроса к Stripe API
            pass
        
        # Формируем сумму
        if instance.payment_type == 'crypto' and instance.crypto_amount and instance.crypto_currency:
            amount_str = f"{instance.crypto_amount} {instance.crypto_currency}"
        else:
            currency_symbols = {
                'usd': '$',
                'eur': '€',
                'rub': '₽'
            }
            symbol = currency_symbols.get(instance.currency, instance.currency.upper())
            amount_str = f"{symbol}{instance.amount} {instance.currency.upper()}"

        # Метод платежа
        payment_method = instance.payment_method or "Неизвестен"

        from accounts.utils_folder.telegram_notifications import escape_markdown
        escaped_donor_name = escape_markdown(donor_name)
        escaped_amount = escape_markdown(amount_str)
        escaped_payment_method = escape_markdown(payment_method)
        
        # Формируем ссылку на донат в админке с динамическим URL
        # В signals нет доступа к request, используем fallback на настройки
        from accounts.utils_folder.telegram_notifications import get_base_url, format_markdown_link
        base_url = get_base_url(None, tenant=instance.tenant)
        admin_path = reverse('admin:donation_donation_change', args=[instance.id])
        admin_url = f"{base_url}{admin_path}"
        
        # Формируем сообщение
        admin_title = "💰 Новый донат из Mini App"
        
        if telegram_id:
            # Если есть email, добавляем его в сообщение
            email_info = ""
            if instance.email:
                escaped_email = escape_markdown(instance.email)
                email_info = f"\n📧 Email: {escaped_email}"
            
            admin_message = (
                f"От: {escaped_donor_name} (ID: {telegram_id}){email_info}\n"
                f"Сумма: {escaped_amount}\n"
                f"Метод: {escaped_payment_method}\n\n"
                f"👉 {format_markdown_link('Посмотреть в админке', admin_url)}"
            )
        else:
            # Если есть email, добавляем его в сообщение
            email_info = ""
            if instance.email:
                escaped_email = escape_markdown(instance.email)
                email_info = f"\n📧 Email: {escaped_email}"
            
            admin_message = (
                f"От: {escaped_donor_name}{email_info}\n"
                f"Сумма: {escaped_amount}\n"
                f"Метод: {escaped_payment_method}\n\n"
                f"👉 {format_markdown_link('Посмотреть в админке', admin_url)}"
            )
        
        notify_all_admins(
            notification_type='donation',
            title=admin_title,
            message=admin_message,
            related_object_id=instance.id,
            related_object_type='donation',
            request=None,
            tenant=instance.tenant
        )
        
        logger.info(f"📤 Отправлено уведомление о донате #{instance.id} из Mini App")
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки уведомления о донате: {e}")

