import json
import logging
import time
from datetime import timedelta

import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify

from tasks.models import Task
from tasks.services.telegram_service import LANGUAGE_TRANSLATIONS

logger = logging.getLogger(__name__)


def _supported_language_code(requested: str) -> str:
    supported = [
        lang_code for lang_code, _ in getattr(settings, 'LANGUAGES', [('en', 'English'), ('ru', 'Russian')])
    ]
    code = (requested or '').lower() or 'en'
    if code in supported:
        return code

    fallback = getattr(settings, 'LANGUAGE_CODE', 'en').split('-')[0].lower() or 'en'
    if fallback in supported:
        return fallback

    return 'en'


def _build_site_task_url(task: Task, translation_language: str) -> str:
    site_url = getattr(settings, 'SITE_URL', 'https://quiz-code.com')
    if not site_url.startswith('http'):
        site_url = f'https://{site_url}'

    topic_name = 'python'
    if task.topic:
        try:
            topic_name = task.topic.name.lower()
        except Exception:
            logger.warning("Не удалось получить topic.name для задачи %s", getattr(task, 'id', None))

    subtopic_name = 'general'
    if task.subtopic:
        try:
            subtopic_name = task.subtopic.name.lower()
        except Exception:
            logger.warning("Не удалось получить subtopic.name для задачи %s", getattr(task, 'id', None))

    subtopic_slug = slugify(subtopic_name)
    difficulty = task.difficulty.lower() if task.difficulty else 'easy'

    language_code = _supported_language_code(translation_language)
    return f"{site_url}/{language_code}/quiz/{topic_name}/{subtopic_slug}/{difficulty}/#task-{task.id}"


def _edit_message_reply_markup(
    chat_id: str,
    message_id: int,
    button_text: str,
    button_url: str,
) -> tuple[bool, str, int]:
    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
    if not token:
        return False, 'TELEGRAM_BOT_TOKEN не настроен', 0

    url = f"https://api.telegram.org/bot{token}/editMessageReplyMarkup"
    reply_markup = {
        'inline_keyboard': [[
            {'text': button_text, 'url': button_url}
        ]]
    }

    payload = {
        'chat_id': chat_id,
        'message_id': message_id,
        'reply_markup': json.dumps(reply_markup),
    }

    try:
        resp = requests.post(url, data=payload, timeout=30)
        if resp.status_code == 429:
            retry_after = 2
            try:
                data = resp.json()
                retry_after = int(data.get('parameters', {}).get('retry_after') or retry_after)
                desc = data.get('description') or 'Too Many Requests'
            except Exception:
                desc = 'Too Many Requests'
            return False, f'429: {desc}', retry_after
        resp.raise_for_status()
        data = resp.json()
        if data.get('ok'):
            return True, 'ok', 0
        return False, data.get('description') or 'unknown telegram error', 0
    except Exception as e:
        return False, str(e), 0


def _clear_message_reply_markup(chat_id: str, message_id: int) -> tuple[bool, str, int]:
    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
    if not token:
        return False, 'TELEGRAM_BOT_TOKEN не настроен', 0

    url = f"https://api.telegram.org/bot{token}/editMessageReplyMarkup"
    payload = {
        'chat_id': chat_id,
        'message_id': message_id,
        'reply_markup': json.dumps({}),
    }

    try:
        resp = requests.post(url, data=payload, timeout=30)
        if resp.status_code == 429:
            retry_after = 2
            try:
                data = resp.json()
                retry_after = int(data.get('parameters', {}).get('retry_after') or retry_after)
                desc = data.get('description') or 'Too Many Requests'
            except Exception:
                desc = 'Too Many Requests'
            return False, f'429: {desc}', retry_after
        resp.raise_for_status()
        data = resp.json()
        if data.get('ok'):
            return True, 'ok', 0
        return False, data.get('description') or 'unknown telegram error', 0
    except Exception as e:
        return False, str(e), 0


class Command(BaseCommand):
    help = 'Обновляет URL в inline-кнопке у уже опубликованных задач в Telegram за последние N дней'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=7)
        parser.add_argument('--limit', type=int, default=0)
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument(
            '--include-poll-offset',
            action='store_true',
            help='Включить попытку обновления reply_markup у самого опроса (offset=0). По умолчанию выключено, чтобы не получать две кнопки.',
        )
        parser.add_argument(
            '--clear-poll-keyboard',
            action='store_true',
            help='Удалить reply_markup у сообщения опроса (task.message_id). Полезно если ранее туда попала кнопка и теперь в канале две кнопки.',
        )
        parser.add_argument(
            '--normalize',
            action='store_true',
            help='Нормализовать состояние: попытаться удалить reply_markup у нескольких сообщений вокруг опроса, затем установить кнопку ровно на одном сообщении.',
        )
        parser.add_argument(
            '--normalize-window',
            type=int,
            default=0,
            help='Дополнительное окно очистки вокруг task.message_id (poll). 0 = выключено (безопасно).',
        )

    def handle(self, *args, **options):
        days = int(options['days'])
        limit = int(options['limit'])
        dry_run = bool(options['dry_run'])
        include_poll_offset = bool(options['include_poll_offset'])
        clear_poll_keyboard = bool(options['clear_poll_keyboard'])
        normalize = bool(options['normalize'])
        normalize_window = int(options['normalize_window'])

        since = timezone.now() - timedelta(days=days)

        qs = Task.objects.filter(
            published=True,
            publish_date__isnull=False,
            publish_date__gte=since,
            message_id__isnull=False,
            group__isnull=False,
        ).select_related('group', 'topic', 'subtopic').prefetch_related('translations').order_by('-publish_date')

        if limit > 0:
            qs = qs[:limit]

        candidates = list(qs)

        self.stdout.write(f"Найдено задач для обновления: {len(candidates)} (days={days}, limit={limit or 'no'})")

        offsets = [1, 2, -1, -2]
        if include_poll_offset:
            offsets = [1, 0, 2, -1, -2]

        updated = 0
        skipped = 0
        failed = 0

        for task in candidates:
            translation = task.translations.first()
            if not translation:
                skipped += 1
                continue

            try:
                final_url = task.external_link or _build_site_task_url(task, translation.language)
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"task_id={task.id}: не удалось сформировать ссылку: {e}"))
                failed += 1
                continue

            lang_trans = LANGUAGE_TRANSLATIONS.get(translation.language, LANGUAGE_TRANSLATIONS.get('en', {}))
            button_text = lang_trans.get('learn_more', 'Learn more')

            chat_id = str(task.group.group_id)
            poll_message_id = int(task.message_id)

            if dry_run:
                self.stdout.write(f"DRY_RUN task_id={task.id} chat_id={chat_id} poll_message_id={poll_message_id} url={final_url}")
                continue

            # Нормализация: сначала чистим reply_markup только у тех message_id,
            # которые мы потенциально будем трогать, чтобы убрать "двойные" и разнобой.
            if normalize:
                candidate_message_ids = {poll_message_id + off for off in offsets}

                # Если явно попросили чистить poll-клавиатуру, добавляем poll message_id.
                if clear_poll_keyboard or include_poll_offset:
                    candidate_message_ids.add(poll_message_id)

                # Опционально: расширить очистку на +/- normalize_window (НЕ по умолчанию)
                extra_window = max(0, normalize_window)
                if extra_window:
                    for off in range(-extra_window, extra_window + 1):
                        candidate_message_ids.add(poll_message_id + off)

                for target_message_id in sorted(candidate_message_ids):
                    ok, msg, retry_after = _clear_message_reply_markup(chat_id, target_message_id)
                    if not ok and retry_after:
                        time.sleep(retry_after)
                        ok, msg, retry_after = _clear_message_reply_markup(chat_id, target_message_id)

                # Небольшая пауза между задачами, чтобы не ловить 429 пачками
                time.sleep(0.2)

            if clear_poll_keyboard:
                ok, msg, retry_after = _clear_message_reply_markup(chat_id, poll_message_id)
                if not ok and retry_after:
                    time.sleep(retry_after)
                    ok, msg, retry_after = _clear_message_reply_markup(chat_id, poll_message_id)
                if ok:
                    self.stdout.write(self.style.SUCCESS(
                        f"task_id={task.id}: удален reply_markup у опроса (message_id={poll_message_id})"
                    ))
                else:
                    self.stdout.write(self.style.WARNING(
                        f"task_id={task.id}: не удалось удалить reply_markup у опроса (message_id={poll_message_id}): {msg}"
                    ))

            success = False
            last_error = ''
            for off in offsets:
                target_message_id = poll_message_id + off
                ok, msg, retry_after = _edit_message_reply_markup(chat_id, target_message_id, button_text, final_url)
                if not ok and retry_after:
                    time.sleep(retry_after)
                    ok, msg, retry_after = _edit_message_reply_markup(chat_id, target_message_id, button_text, final_url)
                if ok:
                    success = True
                    updated += 1
                    self.stdout.write(self.style.SUCCESS(
                        f"task_id={task.id}: обновлено сообщение {target_message_id} (offset={off}) -> {final_url}"
                    ))
                    break
                last_error = msg

            if not success:
                failed += 1
                self.stdout.write(self.style.WARNING(
                    f"task_id={task.id}: не удалось обновить кнопку (poll_message_id={poll_message_id}), ошибка: {last_error}"
                ))

        self.stdout.write(self.style.SUCCESS(f"Готово. updated={updated}, failed={failed}, skipped={skipped}"))
