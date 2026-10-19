from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.urls import reverse
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
import logging

from tenants.branding import email_branding

logger = logging.getLogger(__name__)


def send_password_reset_email(request, user, uidb64, token):
    """Отправить красивое письмо для сброса пароля"""
    try:
        # Формируем URL для сброса пароля
        protocol = 'https' if request.is_secure() else 'http'
        domain = request.get_host()  # Используем текущий домен из запроса
        reset_url = f"{protocol}://{domain}{reverse('accounts:password_reset_confirm', kwargs={'uidb64': uidb64, 'token': token})}"

        # Контекст для шаблонов
        context = {
            'user': user,
            'reset_url': reset_url,
            'uidb64': uidb64,
            'token': token,
            'protocol': protocol,
            'domain': domain,
            **email_branding(getattr(request, 'tenant', None)),
        }
        
        # Рендерим текстовую и HTML версии
        text_content = render_to_string('registration/password_reset_email.txt', context)
        html_content = render_to_string('registration/password_reset_email.html', context)
        
        # Создаем multipart email
        email = EmailMultiAlternatives(
            subject=f"🔐 Password Reset - {context['site_name'] or domain}",
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email]
        )
        
        # Прикрепляем HTML версию
        email.attach_alternative(html_content, "text/html")
        
        # Отправляем
        email.send()
        logger.info(f"Password reset email sent to {user.email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send password reset email to {user.email}: {str(e)}")
        return False 