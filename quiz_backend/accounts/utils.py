from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def send_password_reset_email(user, reset_url):
    """Отправить красивое письмо для сброса пароля"""
    try:
        # Контекст для шаблонов
        context = {
            'user': user,
            'protocol': 'https' if settings.SECURE_SSL_REDIRECT else 'http',
            'domain': settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else 'quiz-code.com',
            'reset_url': reset_url
        }
        
        # Рендерим текстовую и HTML версии
        text_content = render_to_string('registration/password_reset_email.txt', context)
        html_content = render_to_string('registration/password_reset_email.html', context)
        
        # Создаем multipart email
        email = EmailMultiAlternatives(
            subject='🔐 Password Reset - Quiz Project',
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