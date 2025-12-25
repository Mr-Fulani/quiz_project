#!/usr/bin/env python
"""
Тестовый скрипт для проверки публикации в Instagram Reels.
"""
import os
import django
import sys

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from tasks.models import Task, TaskTranslation
from tasks.services.social_media_service import publish_to_platform
from webhooks.models import SocialMediaCredentials

def test_instagram_reels():
    """Тестирование публикации в Instagram Reels."""
    
    print("=" * 60)
    print("Тест публикации в Instagram Reels")
    print("=" * 60)
    
    # 1. Проверка credentials
    print("\n1. Проверка credentials...")
    creds = SocialMediaCredentials.objects.filter(platform='instagram', is_active=True).first()
    if not creds:
        print("❌ Не найдены credentials для Instagram")
        print("\nРешение:")
        print("1. Откройте Django Admin: /admin/webhooks/socialmediacredentials/add/")
        print("2. Создайте новую запись:")
        print("   - Platform: Instagram")
        print("   - Browser Type: Playwright")
        print("   - Headless Mode: False (для первого запуска)")
        print("   - Is Active: True")
        print("   - Access Token: можно оставить пустым")
        return False
    
    print(f"✅ Credentials найдены:")
    print(f"   - Platform: {creds.platform}")
    print(f"   - Browser Type: {creds.browser_type}")
    print(f"   - Headless Mode: {creds.headless_mode}")
    print(f"   - Is Active: {creds.is_active}")
    
    # 2. Проверка задачи с видео
    print("\n2. Поиск задачи с видео...")
    task = Task.objects.filter(video_url__isnull=False, video_url__gt='').first()
    if not task:
        print("❌ Не найдена задача с видео")
        print("\nРешение:")
        print("1. Убедитесь, что есть задачи с заполненным video_url")
        print("2. Или используйте конкретный ID задачи:")
        task_id = input("   Введите ID задачи (или Enter для выхода): ")
        if task_id:
            try:
                task = Task.objects.get(id=int(task_id))
            except Task.DoesNotExist:
                print(f"❌ Задача с ID {task_id} не найдена")
                return False
        else:
            return False
    
    print(f"✅ Задача найдена:")
    print(f"   - ID: {task.id}")
    print(f"   - Video URL: {task.video_url}")
    
    # 3. Проверка переводов
    print("\n3. Проверка переводов...")
    translation = task.translations.first()
    if not translation:
        print("❌ У задачи нет переводов")
        return False
    
    print(f"✅ Перевод найден:")
    print(f"   - Язык: {translation.language}")
    print(f"   - Вопрос: {translation.question[:50]}...")
    
    # 4. Подтверждение публикации
    print("\n" + "=" * 60)
    print("ВНИМАНИЕ: Это реальная публикация в Instagram!")
    print("=" * 60)
    confirm = input("\nПродолжить? (yes/no): ")
    if confirm.lower() not in ['yes', 'y', 'да', 'д']:
        print("Отменено пользователем")
        return False
    
    # 5. Публикация
    print("\n🚀 Начинаем публикацию в Instagram Reels...")
    print("   Это может занять несколько минут...")
    
    try:
        result = publish_to_platform(task, translation, 'instagram_reels')
        
        if result.get('success'):
            print("\n" + "=" * 60)
            print("✅ УСПЕШНО!")
            print("=" * 60)
            print(f"Platform: {result.get('platform')}")
            print(f"Post ID: {result.get('post_id')}")
            if result.get('post_url'):
                print(f"URL: {result.get('post_url')}")
            if result.get('facebook_post_id'):
                print(f"Facebook Reels ID: {result.get('facebook_post_id')}")
                print("   (Кросспостинг в Facebook выполнен)")
            if result.get('instagram_story_id'):
                print(f"Instagram Story ID: {result.get('instagram_story_id')}")
                print("   (Добавлено в Instagram Stories)")
            return True
        else:
            print("\n" + "=" * 60)
            print("❌ ОШИБКА")
            print("=" * 60)
            print(f"Error: {result.get('error')}")
            print("\nВозможные решения:")
            print("1. Проверьте, что Instagram credentials настроены правильно")
            print("2. Убедитесь, что headless_mode=False для первой авторизации")
            print("3. Проверьте логи на наличие дополнительной информации")
            return False
            
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = test_instagram_reels()
    sys.exit(0 if success else 1)

