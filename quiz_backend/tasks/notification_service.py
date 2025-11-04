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


def format_comment_notification(comment) -> str:
    """
    Форматирует уведомление о новом комментарии в Markdown.
    
    Args:
        comment: Объект TaskComment
        
    Returns:
        str: Отформатированное сообщение для Telegram
    """
    try:
        # Получаем информацию об авторе
        try:
            author = MiniAppUser.objects.get(telegram_id=comment.author_telegram_id)
            author_name = author.first_name or author.username or 'Без имени'
            author_username = f"@{author.username}" if author.username else 'нет'
        except MiniAppUser.DoesNotExist:
            author_name = comment.author_username
            author_username = 'нет'
        
        # Информация о задаче
        lang_flag = '🇷🇺' if comment.task_translation.language == 'ru' else '🇬🇧'
        task_info = f"#{comment.task_translation.task_id} ({lang_flag} {comment.task_translation.language.upper()})"
        
        # Текст комментария (обрезаем, если слишком длинный)
        comment_text = comment.text[:200] + ('...' if len(comment.text) > 200 else '')
        
        # Количество изображений
        images_count = comment.images.count()
        images_text = f"\n📷 Изображений: {images_count}" if images_count > 0 else ""
        
        # Информация о родительском комментарии
        parent_info = ""
        if comment.parent_comment:
            try:
                parent_author = MiniAppUser.objects.get(telegram_id=comment.parent_comment.author_telegram_id)
                parent_name = parent_author.first_name or parent_author.username or 'Пользователь'
                parent_username = f"@{parent_author.username}" if parent_author.username else 'нет'
                parent_info = f"\n\n💬 Ответ на комментарий #{comment.parent_comment.id} от {parent_name} ({parent_username}, ID: {comment.parent_comment.author_telegram_id})"
            except MiniAppUser.DoesNotExist:
                parent_info = f"\n\n💬 Ответ на комментарий #{comment.parent_comment.id} от {comment.parent_comment.author_username}"
        
        # Формируем сообщение
        message = f"""💬 *Новый комментарий*

👤 *Автор:* {author_name} ({author_username}, ID: {comment.author_telegram_id})
📝 *Задача:* {task_info}

*Текст:*
"{comment_text}"{images_text}{parent_info}

🔗 Просмотреть в админке:
{settings.SITE_URL}/admin/tasks/taskcomment/{comment.id}/change/
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
        # Информация о репортере
        try:
            reporter = MiniAppUser.objects.get(telegram_id=report.reporter_telegram_id)
            reporter_name = reporter.first_name or reporter.username or 'Без имени'
            reporter_username = f"@{reporter.username}" if reporter.username else 'нет'
        except MiniAppUser.DoesNotExist:
            reporter_name = 'Пользователь не найден'
            reporter_username = 'нет'
        
        # Информация об авторе комментария
        try:
            author = MiniAppUser.objects.get(telegram_id=report.comment.author_telegram_id)
            author_name = author.first_name or author.username or 'Без имени'
            author_username = f"@{author.username}" if author.username else 'нет'
        except MiniAppUser.DoesNotExist:
            author_name = report.comment.author_username
            author_username = 'нет'
        
        # Причина жалобы с иконками
        reason_icons = {
            'spam': '📧',
            'offensive': '⚠️',
            'inappropriate': '🚫',
            'other': '❓'
        }
        reason_icon = reason_icons.get(report.reason, '❓')
        reason_text = report.get_reason_display()
        
        # Текст комментария
        comment_text = report.comment.text[:150] + ('...' if len(report.comment.text) > 150 else '')
        
        # Количество изображений
        images_count = report.comment.images.count()
        images_text = f"\n📷 Изображений: {images_count}" if images_count > 0 else ""
        
        # Описание жалобы (если есть)
        description_text = f'\n📝 *Описание:* "{report.description}"' if report.description else ""
        
        # Общее количество жалоб на комментарий
        total_reports = report.comment.reports_count
        
        # Формируем сообщение
        message = f"""🚨 *Новая жалоба на комментарий*

👤 *Кто пожаловался:* {reporter_name} ({reporter_username}, ID: {report.reporter_telegram_id})
🎯 *На кого:* {author_name} ({author_username}, ID: {report.comment.author_telegram_id})

{reason_icon} *Причина:* {reason_text}{description_text}

💬 *Комментарий #{report.comment.id}:*
"{comment_text}"{images_text}

⚠️ *Всего жалоб на этот комментарий:* {total_reports}

🔗 Просмотреть жалобу:
{settings.SITE_URL}/admin/tasks/taskcommentreport/{report.id}/change/

🔗 Просмотреть комментарий:
{settings.SITE_URL}/admin/tasks/taskcomment/{report.comment.id}/change/
"""
        
        return message
        
    except Exception as e:
        logger.error(f"Ошибка форматирования уведомления о жалобе: {e}")
        return f"🚨 Новая жалоба #{report.id if report else 'N/A'}"


def send_to_all_admins(message: str, parse_mode: str = "Markdown") -> int:
    """
    Отправляет уведомление всем активным администраторам.
    
    Args:
        message: Текст сообщения
        parse_mode: Режим парсинга (Markdown или HTML)
        
    Returns:
        int: Количество успешно отправленных уведомлений
    """
    sent_count = 0
    
    try:
        # Получаем всех активных админов
        admins = TelegramAdmin.objects.filter(is_active=True)
        
        if not admins.exists():
            logger.warning("Нет активных администраторов для отправки уведомлений")
            return 0
        
        for admin in admins:
            try:
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

