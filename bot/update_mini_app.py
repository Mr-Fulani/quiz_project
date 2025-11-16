#!/usr/bin/env python3
"""
Скрипт для автоматического обновления настроек mini app в Telegram.
Обновляет все возможные настройки бота с актуальным WEBAPP_URL.
"""

import os
import asyncio
import sys
import logging
from dotenv import load_dotenv

# Настройка Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "quiz_backend.config.settings")

import django
django.setup()

from aiogram import Bot
from aiogram.types import MenuButtonDefault, MenuButtonWebApp, WebAppInfo

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBAPP_URL = os.getenv('WEBAPP_URL')


async def update_all_bot_settings():
    """
    Обновляет все настройки бота для mini app.
    """
    if not TELEGRAM_BOT_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN не установлен!")
        return False
        
    if not WEBAPP_URL:
        logger.error("❌ WEBAPP_URL не установлен!")
        return False
    
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    
    try:
        # URL для главной страницы мини-приложения
        main_app_url = f"{WEBAPP_URL}/"
        
        logger.info("=" * 60)
        logger.info("🚀 ОБНОВЛЕНИЕ НАСТРОЕК MINI APP")
        logger.info("=" * 60)
        logger.info(f"🔗 WEBAPP_URL: {WEBAPP_URL}")
        logger.info(f"🔗 Главная страница Mini App: {main_app_url}")
        
        # Шаг 1: Получаем информацию о боте
        me = await bot.get_me()
        logger.info(f"🤖 Бот: @{me.username} (ID: {me.id})")
        
        # Шаг 2: Очищаем команды
        logger.info("🧹 Очистка команд бота...")
        await bot.set_my_commands([])
        
        # Шаг 3: Сбрасываем menu button на default
        logger.info("🧹 Сброс menu button на default...")
        await bot.set_chat_menu_button(menu_button=MenuButtonDefault())
        await asyncio.sleep(1)
        
        # Шаг 4: Устанавливаем новый menu button
        logger.info("🔧 Установка нового menu button...")
        # Текст кнопки по умолчанию: "Запустить приложение"
        menu_button_text = os.getenv('TELEGRAM_MENU_BUTTON_TEXT', 'Запустить приложение')
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text=menu_button_text,
                web_app=WebAppInfo(url=main_app_url)
            )
        )
        
        # Шаг 5: Проверяем результат
        updated_menu = await bot.get_chat_menu_button()
        logger.info(f"✅ Обновленный menu button: {updated_menu}")
        
        # Шаг 6: Обновляем описание бота (только если установлена переменная окружения)
        logger.info("📝 Проверка настроек описания бота...")
        desired_description = os.getenv('TELEGRAM_BOT_DESCRIPTION')
        if desired_description:
            logger.info(f"📝 Обновление описания бота: {desired_description}")
            await bot.set_my_description(description=desired_description)
        else:
            logger.info("ℹ️  TELEGRAM_BOT_DESCRIPTION не установлена - пропускаем обновление описания")
        
        # Шаг 7: Обновляем краткое описание (только если установлена переменная окружения)
        desired_short_description = os.getenv('TELEGRAM_BOT_SHORT_DESCRIPTION')
        if desired_short_description:
            logger.info(f"📝 Обновление краткого описания: {desired_short_description}")
            await bot.set_my_short_description(short_description=desired_short_description)
        else:
            logger.info("ℹ️  TELEGRAM_BOT_SHORT_DESCRIPTION не установлена - пропускаем обновление краткого описания")
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ ВСЕ НАСТРОЙКИ ОБНОВЛЕНЫ!")
        logger.info("=" * 60)
        logger.info("\n💡 Что делать дальше:")
        logger.info("   1. Полностью закройте Telegram приложение")
        logger.info("   2. Откройте Telegram заново")
        logger.info("   3. Найдите бота в списке чатов")
        logger.info("   4. Проверьте кнопку 'ОТКРЫТЬ' - она должна открывать новый URL")
        logger.info("   5. Если не помогло, очистите кэш Telegram приложения")
        
        return True
        
    except Exception as e:
        logger.exception(f"❌ Ошибка при обновлении настроек: {e}")
        return False
    finally:
        await bot.session.close()


async def main():
    """
    Главная функция.
    """
    success = await update_all_bot_settings()
    
    if not success:
        logger.error("\n" + "=" * 60)
        logger.error("❌ ОШИБКА! Настройки не были обновлены.")
        logger.error("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
