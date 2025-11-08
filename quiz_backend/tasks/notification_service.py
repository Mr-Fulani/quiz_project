"""
Сервис уведомлений для комментариев и жалоб.

Отправляет уведомления администраторам через Telegram при создании
новых комментариев и жалоб на комментарии.
"""

import logging
from typing import Optional
from django.conf import settings
from accounts.models import TelegramAdmin, MiniAppUser
from accounts.utils_folder.telegram_notifications import send_telegram_notification_sync

logger = logging.getLogger(__name__)


def format_comment_notification(comment, request=None) -> str:
    """
    Форматирует уведомление о новом комментарии в Markdown.
    
    Args:
        comment: Объект TaskComment
        request: Django request для получения правильного base_url (опционально)
        
    Returns:
        str: Отформатированное сообщение для Telegram
    """
    try:
        from accounts.utils_folder.telegram_notifications import (
            get_base_url,
            escape_username_for_markdown,
            format_markdown_link,
            escape_markdown,
        )
        from django.urls import reverse
        
        # Получаем информацию об авторе
        try:
            author = MiniAppUser.objects.get(telegram_id=comment.author_telegram_id)
            author_name = author.first_name or author.username or 'Без имени'
            # Используем escape_username_for_markdown для правильного отображения username
            escaped_username = escape_username_for_markdown(author.username) if author.username else None
            author_username = f"@{escaped_username}" if escaped_username else 'нет'
        except MiniAppUser.DoesNotExist:
            author_name = comment.author_username
            author_username = 'нет'

        escaped_author_name = escape_markdown(author_name)
        
        # Информация о задаче с топиком
        lang_flag = '🇷🇺' if comment.task_translation.language == 'ru' else '🇬🇧'
        task = comment.task_translation.task
        topic_name = escape_markdown(task.topic.name) if task.topic else 'Без топика'
        
        # Добавляем подтопик, если он есть
        subtopic_info = ""
        if task.subtopic:
            subtopic_name = escape_markdown(task.subtopic.name)
            subtopic_info = f" → {subtopic_name}"
        
        task_info = f"#{comment.task_translation.task_id} ({lang_flag} {comment.task_translation.language.upper()}) | {topic_name}{subtopic_info}"
        
        # Текст комментария (обрезаем, если слишком длинный)
        raw_comment_text = comment.text[:200] + ('...' if len(comment.text) > 200 else '')
        comment_text = escape_markdown(raw_comment_text)
        
        # Количество изображений
        images_count = comment.images.count()
        images_text = f"\n📷 Изображений: {images_count}" if images_count > 0 else ""
        
        # Информация о родительском комментарии
        parent_info = ""
        if comment.parent_comment:
            try:
                parent_author = MiniAppUser.objects.get(telegram_id=comment.parent_comment.author_telegram_id)
                parent_name = parent_author.first_name or parent_author.username or 'Пользователь'
                escaped_parent_username = escape_username_for_markdown(parent_author.username) if parent_author.username else None
                parent_username = f"@{escaped_parent_username}" if escaped_parent_username else 'нет'
                escaped_parent_name = escape_markdown(parent_name)
                parent_info = (
                    f"\n\n💬 Ответ на комментарий #{comment.parent_comment.id} от {escaped_parent_name}"
                    f" ({parent_username}, ID: {comment.parent_comment.author_telegram_id})"
                )
            except MiniAppUser.DoesNotExist:
                fallback_parent_name = escape_markdown(comment.parent_comment.author_username or 'Пользователь')
                parent_info = f"\n\n💬 Ответ на комментарий #{comment.parent_comment.id} от {fallback_parent_name}"
        
        # Формируем ссылку с динамическим base_url
        base_url = get_base_url(request)
        admin_path = reverse('admin:tasks_taskcomment_change', args=[comment.id])
        admin_url = f"{base_url}{admin_path}"
        
        # Формируем сообщение
        message = f"""💬 *Новый комментарий*

👤 *Автор:* {escaped_author_name} ({author_username}, ID: {comment.author_telegram_id})
📝 *Задача:* {task_info}

*Текст:*
"{comment_text}"{images_text}{parent_info}

🔗 {format_markdown_link('Просмотреть в админке', admin_url)}
"""
        
        return message
        
    except Exception as e:
        logger.error(f"Ошибка форматирования уведомления о комментарии: {e}")
        return f"💬 Новый комментарий #{comment.id if comment else 'N/A'}"


def format_report_notification(report) -> str:
    """
    Форматирует уведомление о новой жалобе в Markdown.
    
    Args:
        report: Объект TaskCommentReport
        
    Returns:
        str: Отформатированное сообщение для Telegram
    """
    try:
        from accounts.utils_folder.telegram_notifications import (
            format_markdown_link,
            escape_username_for_markdown,
            escape_markdown,
        )

        # Информация о репортере
        try:
            reporter = MiniAppUser.objects.get(telegram_id=report.reporter_telegram_id)
            reporter_name = reporter.first_name or reporter.username or 'Без имени'
            reporter_username = f"@{escape_username_for_markdown(reporter.username)}" if reporter.username else 'нет'
        except MiniAppUser.DoesNotExist:
            reporter_name = 'Пользователь не найден'
            reporter_username = 'нет'

        escaped_reporter_name = escape_markdown(reporter_name)
        
        # Информация об авторе комментария
        try:
            author = MiniAppUser.objects.get(telegram_id=report.comment.author_telegram_id)
            author_name = author.first_name or author.username or 'Без имени'
            author_username = f"@{escape_username_for_markdown(author.username)}" if author.username else 'нет'
        except MiniAppUser.DoesNotExist:
            author_name = report.comment.author_username
            author_username = 'нет'

        escaped_author_name = escape_markdown(author_name)
        
        # Причина жалобы с иконками
        reason_icons = {
            'spam': '📧',
            'offensive': '⚠️',
            'inappropriate': '🚫',
            'other': '❓'
        }
        reason_icon = reason_icons.get(report.reason, '❓')
        reason_text = escape_markdown(report.get_reason_display())
        
        # Текст комментария
        raw_comment_text = report.comment.text[:150] + ('...' if len(report.comment.text) > 150 else '')
        comment_text = escape_markdown(raw_comment_text)
        
        # Количество изображений
        images_count = report.comment.images.count()
        images_text = f"\n📷 Изображений: {images_count}" if images_count > 0 else ""
        
        # Описание жалобы (если есть)
        description_text = ''
        if report.description:
            escaped_description = escape_markdown(report.description)
            description_text = f'\n📝 *Описание:* "{escaped_description}"'
        
        # Общее количество жалоб на комментарий
        total_reports = report.comment.reports_count
        
        # Формируем сообщение
        message = f"""🚨 *Новая жалоба на комментарий*

👤 *Кто пожаловался:* {escaped_reporter_name} ({reporter_username}, ID: {report.reporter_telegram_id})
🎯 *На кого:* {escaped_author_name} ({author_username}, ID: {report.comment.author_telegram_id})

{reason_icon} *Причина:* {reason_text}{description_text}

💬 *Комментарий #{report.comment.id}:*
"{comment_text}"{images_text}

⚠️ *Всего жалоб на этот комментарий:* {total_reports}

🔗 {format_markdown_link('Просмотреть жалобу', f"{settings.SITE_URL}/admin/tasks/taskcommentreport/{report.id}/change/")}

🔗 {format_markdown_link('Просмотреть комментарий', f"{settings.SITE_URL}/admin/tasks/taskcomment/{report.comment.id}/change/")}
"""
        
        return message
        
    except Exception as e:
        logger.error(f"Ошибка форматирования уведомления о жалобе: {e}")
        return f"🚨 Новая жалоба #{report.id if report else 'N/A'}"


def send_to_all_admins(message: str, parse_mode: str = "Markdown") -> int:
    """
    Отправляет уведомление всем активным администраторам.
    Проверяет настройку notifications_enabled из MiniAppUser перед отправкой.
    
    Args:
        message: Текст сообщения
        parse_mode: Режим парсинга (Markdown или HTML)
        
    Returns:
        int: Количество успешно отправленных уведомлений
    """
    sent_count = 0
    
    try:
        from accounts.models import MiniAppUser
        
        # Получаем всех активных админов
        admins = TelegramAdmin.objects.filter(is_active=True)
        
        if not admins.exists():
            logger.warning("Нет активных администраторов для отправки уведомлений")
            return 0
        
        for admin in admins:
            try:
                # Проверяем настройку notifications_enabled из MiniAppUser
                # Связь может быть через telegram_admin или через telegram_id
                mini_app_user = None
                try:
                    # Пытаемся получить через связь telegram_admin
                    if admin.mini_app_user:
                        mini_app_user = admin.mini_app_user
                    else:
                        # Если связи нет, ищем по telegram_id
                        mini_app_user = MiniAppUser.objects.filter(telegram_id=admin.telegram_id).first()
                except Exception as e:
                    logger.debug(f"Ошибка при получении MiniAppUser для админа {admin.telegram_id}: {e}")
                    # Продолжаем отправку, если не удалось получить MiniAppUser
                    mini_app_user = None
                
                # Проверяем настройку уведомлений
                if mini_app_user and not mini_app_user.notifications_enabled:
                    logger.info(f"Уведомления отключены для админа {admin.telegram_id}, пропускаем отправку")
                    continue
                
                success = send_telegram_notification_sync(
                    telegram_id=admin.telegram_id,
                    message=message,
                    parse_mode=parse_mode
                )
                
                if success:
                    sent_count += 1
                    logger.info(f"Уведомление отправлено админу {admin.telegram_id}")
                else:
                    logger.warning(f"Не удалось отправить уведомление админу {admin.telegram_id}")
                    
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления админу {admin.telegram_id}: {e}")
        
        logger.info(f"Уведомления отправлены {sent_count} из {admins.count()} админов")
        
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомлений админам: {e}")
    
    return sent_count


def notify_admins_new_comment(comment) -> int:
    """
    Уведомляет администраторов о новом комментарии.
    
    Args:
        comment: Объект TaskComment
        
    Returns:
        int: Количество успешно отправленных уведомлений
    """
    try:
        message = format_comment_notification(comment)
        return send_to_all_admins(message)
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления о новом комментарии: {e}")
        return 0


def notify_admins_new_report(report) -> int:
    """
    Уведомляет администраторов о новой жалобе.
    
    Args:
        report: Объект TaskCommentReport
        
    Returns:
        int: Количество успешно отправленных уведомлений
    """
    try:
        message = format_report_notification(report)
        return send_to_all_admins(message)
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления о новой жалобе: {e}")
        return 0

