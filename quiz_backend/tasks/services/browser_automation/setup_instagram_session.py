#!/usr/bin/env python
"""
Скрипт для первоначальной авторизации в Instagram локально.
Запускается на вашем компьютере (не в Docker) для сохранения сессии.

Использование:
    python manage.py runscript setup_instagram_session --script-args <credentials_id>

Или через Django shell:
    python manage.py shell
    >>> from tasks.services.browser_automation.setup_instagram_session import setup_session
    >>> from webhooks.models import SocialMediaCredentials
    >>> creds = SocialMediaCredentials.objects.get(platform='instagram')
    >>> setup_session(creds.id)
"""
import os
import sys
import django

# Настройка Django
if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()

from webhooks.models import SocialMediaCredentials
from tasks.services.browser_automation.platforms.instagram_reels import InstagramReelsAutomation
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def setup_session(credentials_id=None):
    """
    Выполняет первоначальную авторизацию в Instagram локально.
    Браузер откроется видимым, вы авторизуетесь, сессия сохранится.
    
    Args:
        credentials_id: ID учетных данных Instagram (если None - берет первый)
    """
    try:
        if credentials_id:
            credentials = SocialMediaCredentials.objects.get(id=credentials_id, platform='instagram')
        else:
            credentials = SocialMediaCredentials.objects.filter(platform='instagram').first()
            if not credentials:
                logger.error("❌ Не найдены учетные данные Instagram")
                logger.info("Создайте их в Django Admin: /admin/webhooks/socialmediacredentials/")
                return False
        
        logger.info(f"📝 Используются учетные данные: {credentials.id} ({credentials.platform})")
        logger.info("🌐 Запуск браузера для авторизации...")
        logger.info("⚠️ ВАЖНО: Браузер откроется. Авторизуйтесь в Instagram вручную.")
        logger.info("⏳ После авторизации скрипт автоматически сохранит сессию.")
        
        # Создаем автоматизацию (браузер будет видимым)
        automation = InstagramReelsAutomation(
            credentials=credentials,
            browser_type='playwright'
        )
        
        # Получаем браузер (будет видимым, т.к. не Docker)
        browser = automation._get_browser()
        automation.browser = browser  # Сохраняем браузер в объект автоматизации
        
        # Запускаем браузер
        if not browser.start_browser():
            logger.error("❌ Не удалось запустить браузер")
            return False
        
        # Авторизуемся (браузер откроется, вы авторизуетесь вручную)
        if automation._login():
            logger.info("✅ Авторизация успешна! Сессия сохранена.")
            logger.info("🎉 Теперь можно использовать эту сессию в Docker (headless режим)")
            browser.close_browser()
            return True
        else:
            logger.error("❌ Авторизация не удалась")
            browser.close_browser()
            return False
            
    except SocialMediaCredentials.DoesNotExist:
        logger.error(f"❌ Учетные данные с ID={credentials_id} не найдены")
        return False
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}", exc_info=True)
        return False


if __name__ == '__main__':
    # Проверяем, что Django настроен
    try:
        from django.conf import settings
        if not settings.configured:
            django.setup()
    except:
        pass
    
    credentials_id = None
    if len(sys.argv) > 1:
        try:
            credentials_id = int(sys.argv[1])
        except ValueError:
            logger.error("❌ ID должен быть числом")
            logger.info("Использование: python setup_instagram_session.py [credentials_id]")
            sys.exit(1)
    
    success = setup_session(credentials_id)
    sys.exit(0 if success else 1)

