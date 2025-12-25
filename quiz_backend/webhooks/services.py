import logging
import time
import uuid
from typing import Any, Dict, List

import requests
from django.conf import settings
from platforms.models import TelegramGroup
from accounts.models import CustomUser
from tasks.models import Task
from tasks.services.webhook_service import create_full_webhook_data, create_bulk_webhook_data, create_russian_only_webhook_data, create_english_only_webhook_data

from webhooks.models import Webhook

logger = logging.getLogger(__name__)


class TelegramWebhookHandler:
    """
    Обработчик вебхуков от Telegram.
    Содержит бизнес-логику обработки различных типов обновлений.
    """
    
    def process_update(self, update):
        """Обрабатывает обновление от Telegram."""
        if 'message' in update:
            self._handle_message(update['message'])
        elif 'callback_query' in update:
            self._handle_callback_query(update['callback_query'])

    def _handle_message(self, message):
        """Обрабатывает входящее сообщение."""
        if 'text' in message:
            if message['text'].startswith('/'):
                self._handle_command(message)
            else:
                self._handle_answer(message)

    def _handle_command(self, message):
        """Обрабатывает команды бота."""
        command = message['text'].split()[0].lower()
        if command == '/start':
            self._send_welcome_message(message['chat']['id'])
        elif command == '/help':
            self._send_help_message(message['chat']['id'])

    def _send_welcome_message(self, chat_id):
        """Отправляет приветственное сообщение."""
        message = "Добро пожаловать! Я бот для проверки знаний."
        self._send_message(chat_id, message)

    def _send_help_message(self, chat_id):
        """Отправляет справочное сообщение."""
        message = "Доступные команды:\n/start - Начать\n/help - Помощь"
        self._send_message(chat_id, message)

    def _send_message(self, chat_id, text):
        """Отправляет сообщение в Telegram."""
        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            'chat_id': chat_id,
            'text': text
        }
        try:
            requests.post(url, json=data)
        except Exception:
            pass  # Логирование ошибки в реальном приложении

    def _handle_answer(self, message):
        """Обрабатывает ответ на вопрос."""
        # Логика обработки ответов
        pass

    def _handle_callback_query(self, callback_query):
        """Обрабатывает callback query от инлайн кнопок."""
        # Логика обработки callback query
        pass

    def setup_webhook(self):
        """Настраивает вебхук в Telegram Bot API."""
        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/setWebhook"
        webhook_url = f"{settings.BASE_URL}/api/webhooks/telegram/"
        
        data = {
            'url': webhook_url,
            'secret_token': settings.TELEGRAM_WEBHOOK_SECRET,
        }
        
        response = requests.post(url, json=data)
        return response.status_code == 200 


WEBHOOK_TIMEOUT = getattr(settings, "WEBHOOK_TIMEOUT", 15)  # Уменьшен таймаут
WEBHOOK_RETRIES = getattr(settings, "WEBHOOK_RETRIES", 2)  # Уменьшено количество повторных попыток
WEBHOOK_RETRY_DELAY = getattr(settings, "WEBHOOK_RETRY_DELAY", 1)  # Уменьшена задержка
WEBHOOK_MAX_CONCURRENT = getattr(settings, "WEBHOOK_MAX_CONCURRENT", 3)  # Максимум одновременных запросов


def _build_headers(payload: Dict[str, Any]) -> Dict[str, str]:
    """Формирует заголовки для каждой отправки вебхука."""
    return {
        'Content-Type': 'application/json',
        'X-Request-ID': str(uuid.uuid4()),
        'X-Webhook-ID': payload.get("id", ""),
        'X-Webhook-Type': payload.get("type", ""),
        'X-Webhook-Timestamp': payload.get("timestamp", ""),
    }


def send_task_published_webhook(webhook_url: str, data: Dict[str, Any]) -> bool:
    """
    Отправляет один вебхук с повтором при ошибках.

    Возвращает True только если получен успешный HTTP-ответ.
    """
    headers = _build_headers(data)
    for attempt in range(1, WEBHOOK_RETRIES + 1):
        try:
            logger.info("Попытка %s/%s отправки вебхука на %s", attempt, WEBHOOK_RETRIES, webhook_url)
            response = requests.post(
                webhook_url,
                json=data,
                headers=headers,
                timeout=WEBHOOK_TIMEOUT
            )

            logger.info(
                "Вебхук %s: статус=%s, тело=%s",
                webhook_url,
                response.status_code,
                response.text[:400]
            )

            if response.status_code in {200, 201, 202, 204}:
                logger.info("✅ Вебхук отправлен: %s", webhook_url)
                return True
        except requests.RequestException as exc:
            logger.warning("⚠️ Ошибка при попытке %s отправки на %s: %s", attempt, webhook_url, exc)

        if attempt < WEBHOOK_RETRIES:
            delay = WEBHOOK_RETRY_DELAY * attempt
            logger.info("⏳ Ожидание %s секунд перед повторной попыткой", delay)
            time.sleep(delay)

    logger.error("❌ Все попытки отправки вебхука на %s провалились", webhook_url)
    return False


def send_webhooks_for_task(task: "Task") -> Dict[str, Any]:
    """
    Формирует данные задачи и отправляет их на все активные вебхуки.
    Для вебхуков типа 'russian_only' отправляет только русские данные.
    """
    # Группируем вебхуки по типу
    webhooks = list(Webhook.objects.filter(is_active=True))
    if not webhooks:
        logger.info("Нет активных вебхуков для задачи %s", task.id)
        return {"total": 0, "success": 0, "failed": 0, "details": []}

    regular_webhooks = []
    russian_only_webhooks = []
    english_only_webhooks = []

    for webhook in webhooks:
        if webhook.webhook_type == 'russian_only':
            russian_only_webhooks.append(webhook)
        elif webhook.webhook_type == 'english_only':
            english_only_webhooks.append(webhook)
        else:
            regular_webhooks.append(webhook)

    results: List[Dict[str, Any]] = []
    success_count = 0

    # Отправка на обычные вебхуки
    if regular_webhooks:
        payload = create_full_webhook_data(task)
        for webhook in regular_webhooks:
            success = send_task_published_webhook(webhook.url, payload)
            results.append({
                "url": webhook.url,
                "service": webhook.service_name or "Неизвестный сервис",
                "type": webhook.webhook_type,
                "success": success,
            })
            if success:
                success_count += 1
            else:
                # 🛑 Автоматическая деактивация при неудаче
                try:
                    webhook.is_active = False
                    webhook.save(update_fields=['is_active'])
                    logger.warning(f"🛑 Вебхук '{webhook.service_name or 'Неизвестный'}' ({webhook.url}) деактивирован после неудачной отправки")
                except Exception as e:
                    logger.error(f"❌ Ошибка при деактивации вебхука {webhook.url}: {e}")

    # Отправка на русскоязычные вебхуки
    if russian_only_webhooks:
        # Создаем payload только с русскими данными
        full_payload = create_full_webhook_data(task)
        russian_translations = [trans for trans in full_payload.get("translations", []) if trans.get("language") == "ru"]

        if russian_translations:  # Отправляем только если есть русский перевод
            russian_payload = full_payload.copy()
            russian_payload["type"] = "quiz_published_russian_only"
            russian_payload["translations"] = russian_translations

            for webhook in russian_only_webhooks:
                success = send_task_published_webhook(webhook.url, russian_payload)
                results.append({
                    "url": webhook.url,
                    "service": webhook.service_name or "Неизвестный сервис",
                    "type": webhook.webhook_type,
                    "success": success,
                })
                if success:
                    success_count += 1
                else:
                    # 🛑 Автоматическая деактивация при неудаче
                    try:
                        webhook.is_active = False
                        webhook.save(update_fields=['is_active'])
                        logger.warning(f"🛑 Русскоязычный вебхук '{webhook.service_name or 'Неизвестный'}' ({webhook.url}) деактивирован после неудачной отправки")
                    except Exception as e:
                        logger.error(f"❌ Ошибка при деактивации русскоязычного вебхука {webhook.url}: {e}")

    # Отправка на англоязычные вебхуки
    if english_only_webhooks:
        # Создаем payload только с английскими данными
        full_payload = create_full_webhook_data(task)
        english_translations = [trans for trans in full_payload.get("translations", []) if trans.get("language") == "en"]

        if english_translations:  # Отправляем только если есть английский перевод
            english_payload = full_payload.copy()
            english_payload["type"] = "quiz_published_english_only"
            english_payload["translations"] = english_translations

            for webhook in english_only_webhooks:
                success = send_task_published_webhook(webhook.url, english_payload)
                results.append({
                    "url": webhook.url,
                    "service": webhook.service_name or "Неизвестный сервис",
                    "type": webhook.webhook_type,
                    "success": success,
                })
                if success:
                    success_count += 1
                else:
                    # 🛑 Автоматическая деактивация при неудаче
                    try:
                        webhook.is_active = False
                        webhook.save(update_fields=['is_active'])
                        logger.warning(f"🛑 Англоязычный вебхук '{webhook.service_name or 'Неизвестный'}' ({webhook.url}) деактивирован после неудачной отправки")
                    except Exception as e:
                        logger.error(f"❌ Ошибка при деактивации англоязычного вебхука {webhook.url}: {e}")

    failed_count = len(results) - success_count
    logger.info(
        "Вебхуки: отправлено=%s, неудачных=%s, всего=%s",
        success_count,
        failed_count,
        len(results),
    )

    return {
        "total": len(results),
        "success": success_count,
        "failed": failed_count,
        "details": results,
    }


def send_webhooks_for_bulk_tasks(tasks: List["Task"], include_video: bool = False) -> Dict[str, Any]:
    """
    Формирует агрегированные данные и отправляет их на все активные вебхуки.
    Для вебхуков типа 'russian_only' отправляет только русские данные.

    Args:
        tasks: Список задач для отправки
        include_video: Если True, включает видео URL в payload
    """
    if not tasks:
        logger.info("Нет опубликованных задач для отправки сводного вебхука.")
        return {"total": 0, "success": 0, "failed": 0, "details": []}

    webhooks = list(Webhook.objects.filter(is_active=True))
    if not webhooks:
        logger.info("Нет активных вебхуков для сводной отправки")
        return {"total": 0, "success": 0, "failed": 0, "details": []}

    # Группируем вебхуки по типу
    regular_webhooks = []
    russian_only_webhooks = []
    english_only_webhooks = []

    for webhook in webhooks:
        if webhook.webhook_type == 'russian_only':
            russian_only_webhooks.append(webhook)
        elif webhook.webhook_type == 'english_only':
            english_only_webhooks.append(webhook)
        else:
            regular_webhooks.append(webhook)

    results: List[Dict[str, Any]] = []
    success_count = 0

    # Отправка на обычные вебхуки
    if regular_webhooks:
        payload = create_bulk_webhook_data(tasks)
        for webhook in regular_webhooks:
            success = send_task_published_webhook(webhook.url, payload)
            results.append({
                "url": webhook.url,
                "service": webhook.service_name or "Неизвестный сервис",
                "type": webhook.webhook_type,
                "success": success,
            })
            if success:
                success_count += 1
            else:
                # 🛑 Автоматическая деактивация при неудаче
                try:
                    webhook.is_active = False
                    webhook.save(update_fields=['is_active'])
                    logger.warning(f"🛑 Вебхук '{webhook.service_name or 'Неизвестный'}' ({webhook.url}) деактивирован после неудачной отправки")
                except Exception as e:
                    logger.error(f"❌ Ошибка при деактивации вебхука {webhook.url}: {e}")

    # Отправка на русскоязычные вебхуки
    if russian_only_webhooks:
        russian_payload = create_russian_only_webhook_data(tasks)
        published_tasks_count = len(russian_payload.get("published_tasks", []))
        logger.info(f"🇷🇺 Русские вебхуки: {len(russian_only_webhooks)} вебхуков, {published_tasks_count} задач для отправки")
        if russian_payload.get("published_tasks"):  # Отправляем только если есть задачи с русским переводом
            for webhook in russian_only_webhooks:
                success = send_task_published_webhook(webhook.url, russian_payload)
                results.append({
                    "url": webhook.url,
                    "service": webhook.service_name or "Неизвестный сервис",
                    "type": webhook.webhook_type,
                    "success": success,
                })
                if success:
                    success_count += 1
                else:
                    # 🛑 Автоматическая деактивация при неудаче
                    try:
                        webhook.is_active = False
                        webhook.save(update_fields=['is_active'])
                        logger.warning(f"🛑 Русскоязычный вебхук '{webhook.service_name or 'Неизвестный'}' ({webhook.url}) деактивирован после неудачной отправки")
                    except Exception as e:
                        logger.error(f"❌ Ошибка при деактивации русскоязычного вебхука {webhook.url}: {e}")
        else:
            logger.info("🇷🇺 Русские вебхуки: пропущены - нет задач с русским переводом")

    # Отправка на англоязычные вебхуки
    if english_only_webhooks:
        english_payload = create_english_only_webhook_data(tasks)
        published_tasks_count = len(english_payload.get("published_tasks", []))
        logger.info(f"🇺🇸 Английские вебхуки: {len(english_only_webhooks)} вебхуков, {published_tasks_count} задач для отправки")
        if english_payload.get("published_tasks"):  # Отправляем только если есть задачи с английским переводом
            for webhook in english_only_webhooks:
                success = send_task_published_webhook(webhook.url, english_payload)
                results.append({
                    "url": webhook.url,
                    "service": webhook.service_name or "Неизвестный сервис",
                    "type": webhook.webhook_type,
                    "success": success,
                })
                if success:
                    success_count += 1
                else:
                    # 🛑 Автоматическая деактивация при неудаче
                    try:
                        webhook.is_active = False
                        webhook.save(update_fields=['is_active'])
                        logger.warning(f"🛑 Англоязычный вебхук '{webhook.service_name or 'Неизвестный'}' ({webhook.url}) деактивирован после неудачной отправки")
                    except Exception as e:
                        logger.error(f"❌ Ошибка при деактивации англоязычного вебхука {webhook.url}: {e}")
        else:
            logger.info("🇺🇸 Английские вебхуки: пропущены - нет задач с английским переводом")

    failed_count = len(results) - success_count
    logger.info(
        "Сводные вебхуки: отправлено=%s, неудачных=%s, всего=%s",
        success_count,
        failed_count,
        len(results),
    )

    return {
        "total": len(results),
        "success": success_count,
        "failed": failed_count,
        "details": results,
    }