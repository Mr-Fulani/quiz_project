# bot/handlers/feedback.py

import datetime
import logging
import os
from datetime import datetime

from aiogram import types, Router, Bot
from aiogram.filters import StateFilter, BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.models import FeedbackMessage, FeedbackReply, TelegramAdmin
from bot.database.database import get_session, AsyncSessionMaker  # Импорт из database.py
from bot.keyboards.quiz_keyboards import get_feedback_keyboard
from bot.states.admin_states import FeedbackStates
from bot.utils.markdownV2 import escape_markdown, format_user_link

# Инициализация маршрутизатора
router = Router(name="feedback_router")

# Настройка логирования
logger = logging.getLogger(__name__)


def format_url_link(text: str, url: str) -> str:
    """
    Формирует MarkdownV2-ссылку на URL.
    
    Args:
        text: Текст ссылки
        url: URL адрес
        
    Returns:
        str: Отформатированная ссылка в формате MarkdownV2
    """
    escaped_text = escape_markdown(text)
    # Для URL экранируем только скобки и подчеркивания, которые могут сломать ссылку
    escaped_url = url.replace('(', '\\(').replace(')', '\\)').replace('_', '\\_')
    return f"[{escaped_text}]({escaped_url})"


async def notify_admins_about_feedback(
    bot: Bot,
    db_session: AsyncSession,
    feedback: FeedbackMessage,
    user: types.User
) -> None:
    """
    Отправляет уведомление админам о новом сообщении обратной связи из бота.
    
    Args:
        bot: Экземпляр бота
        db_session: Сессия базы данных
        feedback: Объект FeedbackMessage
        user: Пользователь, отправивший сообщение
    """
    logger.info(f"🔔 Начало отправки уведомления о feedback #{feedback.id} от пользователя {user.id}")
    try:
        # Получаем всех активных админов из базы данных
        admins_result = await db_session.execute(
            select(TelegramAdmin).where(TelegramAdmin.is_active == True)
        )
        admins = admins_result.scalars().all()
        
        logger.info(f"📋 Найдено {len(admins)} активных админов")
        
        if not admins:
            logger.warning("⚠️ Нет активных админов для отправки уведомления о feedback")
            return
        
        # Получаем базовый URL для ссылки на админку
        base_url = os.getenv('SITE_URL', 'https://quiz-code.com')
        # Убираем поддомены если есть
        if 'mini.' in base_url:
            base_url = base_url.replace('mini.', '')
        
        # Формируем ссылку на feedback в админке Django
        admin_path = f"/admin/feedback/feedbackmessage/{feedback.id}/change/"
        admin_url = f"{base_url}{admin_path}"
        
        # Формируем информацию о пользователе
        user_link = format_user_link(user.username, user.id)
        username_display = f"@{escape_markdown(user.username)}" if user.username else escape_markdown("нет")
        
        # Экранируем сообщение для MarkdownV2 (ограничиваем длину)
        message_preview = feedback.message[:200] + "..." if len(feedback.message) > 200 else feedback.message
        escaped_message = escape_markdown(message_preview)
        
        # Формируем ссылку на админку
        admin_link = format_url_link("Посмотреть в админке", admin_url)
        
        # Формируем сообщение для админов (для Telegram с MarkdownV2)
        admin_title = escape_markdown("📩 Новое обращение в поддержку")
        admin_message_telegram = (
            f"{admin_title}\n\n"
            f"От: {user_link} \\(ID: {feedback.user_id}\\)\n"
            f"Username: {username_display}\n"
            f"Категория: {escape_markdown(feedback.category or 'other')}\n"
            f"Источник: {escape_markdown('Telegram Bot')}\n\n"
            f"Сообщение: {escaped_message}\n\n"
            f"👉 {admin_link}"
        )
        
        # Формируем сообщение для БД (без Markdown форматирования)
        username_plain = f"@{user.username}" if user.username else "нет"
        message_preview_plain = feedback.message[:200] + "..." if len(feedback.message) > 200 else feedback.message
        admin_title_plain = "📩 Новое обращение в поддержку"
        admin_message_db = (
            f"{admin_title_plain}\n\n"
            f"От: {username_plain} (ID: {feedback.user_id})\n"
            f"Username: {username_plain}\n"
            f"Категория: {feedback.category or 'other'}\n"
            f"Источник: Telegram Bot\n\n"
            f"Сообщение: {message_preview_plain}\n\n"
            f"👉 Посмотреть в админке: {admin_url}"
        )
        
        # Отправляем уведомление каждому админу
        sent_count = 0
        for admin in admins:
            try:
                await bot.send_message(
                    chat_id=admin.telegram_id,
                    text=admin_message_telegram,
                    parse_mode="MarkdownV2"
                )
                sent_count += 1
                logger.debug(f"Уведомление о feedback #{feedback.id} отправлено админу {admin.telegram_id} (@{admin.username or 'None'})")
            except Exception as e:
                logger.warning(f"Не удалось отправить уведомление о feedback админу {admin.telegram_id}: {e}")
        
        logger.error(f"🔴 DEBUG: После цикла отправки уведомлений для feedback #{feedback.id}, sent_count={sent_count}")
        
        # Создаем запись уведомления в таблице notifications (Django модель) ПЕРЕД финальным сообщением
        logger.error(f"🔴 DEBUG: ДО создания записи уведомления для feedback #{feedback.id}, sent_count={sent_count}")
        logger.error(f"🔴 DEBUG: Начинаем создание записи уведомления в БД для feedback #{feedback.id}")
        logger.info(f"📝 Начинаем создание записи уведомления в БД для feedback #{feedback.id}")
        try:
            # Используем правильный синтаксис для параметризованного запроса
            sql_query = text("""
                INSERT INTO notifications 
                (recipient_telegram_id, is_admin_notification, notification_type, title, message, 
                 related_object_id, related_object_type, is_read, sent_to_telegram, created_at)
                VALUES 
                (NULL, :is_admin_notification, :notification_type, :title, :message, 
                 :related_object_id, :related_object_type, :is_read, :sent_to_telegram, NOW())
            """)
            
            # Ограничиваем длину title и message для БД
            title_for_db = admin_title_plain[:255] if len(admin_title_plain) > 255 else admin_title_plain
            message_for_db = admin_message_db[:5000] if len(admin_message_db) > 5000 else admin_message_db
            
            params = {
                'is_admin_notification': True,
                'notification_type': 'feedback',
                'title': title_for_db,
                'message': message_for_db,
                'related_object_id': feedback.id,
                'related_object_type': 'feedback',
                'is_read': False,
                'sent_to_telegram': sent_count > 0
            }
            
            logger.error(f"🔴 DEBUG: Параметры для INSERT: notification_type={params['notification_type']}, related_object_id={params['related_object_id']}")
            logger.debug(f"Параметры для INSERT: {params}")
            
            logger.error(f"🔴 DEBUG: Выполняем SQL запрос...")
            result = await db_session.execute(sql_query, params)
            logger.error(f"🔴 DEBUG: SQL запрос выполнен, делаем commit...")
            await db_session.commit()
            logger.error(f"🔴 DEBUG: Commit выполнен, rows affected: {result.rowcount}")
            logger.info(f"📝 Создана запись уведомления в БД для feedback #{feedback.id}, rows affected: {result.rowcount}")
        except Exception as e:
            logger.error(f"❌ Ошибка создания записи уведомления в БД для feedback #{feedback.id}: {e}", exc_info=True)
            try:
                await db_session.rollback()
                logger.error(f"🔴 DEBUG: Rollback выполнен")
            except Exception as rollback_error:
                logger.error(f"❌ Ошибка при rollback: {rollback_error}")
        
        logger.info(f"Уведомление о feedback #{feedback.id} отправлено {sent_count} из {len(admins)} админам")
        
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомлений админам о feedback: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")


# Обработчик кнопки "🆘 Поддержка-Support"
@router.message(lambda message: message.text and message.text.lower() == "🆘 поддержка-support")
async def handle_write_to_admin(message: types.Message):
    await message.answer("Ваше сообщение для администратора. Напишите текст, и он будет передан.")



# Фильтр для сообщений пользователей
class UserMessageFilter(BaseFilter):
    async def __call__(self, message: Message, state: FSMContext) -> bool:
        current_state = await state.get_state()
        return (
            message.text
            and message.text.lower() != "🆘 поддержка-support"
            and current_state != FeedbackStates.awaiting_reply
        )

# Обработчик для сохранения сообщения пользователя
@router.message(UserMessageFilter())
async def save_feedback_message(message: types.Message):
    logger.info(f"📝 Получено сообщение обратной связи от пользователя {message.from_user.id} (@{message.from_user.username})")
    async with get_session() as session:
        feedback = FeedbackMessage(
            user_id=message.from_user.id,
            username=message.from_user.username,
            message=message.text,
            created_at=datetime.utcnow(),
            is_processed=False,
            source='bot',  # Указываем источник сообщения
            category='other'  # Категория по умолчанию
        )
        session.add(feedback)
        await session.flush()  # Получаем ID без commit
        feedback_id = feedback.id
        await session.commit()
        
        logger.info(f"💾 Сохранено сообщение обратной связи ID={feedback_id} от пользователя {message.from_user.id}")
    
    # Отправляем уведомление админам о новом сообщении обратной связи (вне контекста сессии)
    logger.info(f"📤 Вызов notify_admins_about_feedback для feedback #{feedback_id}")
    try:
        # Создаем новую сессию для уведомлений
        async with get_session() as notification_session:
            # Получаем feedback заново для новой сессии
            feedback_for_notification = await notification_session.get(FeedbackMessage, feedback_id)
            if feedback_for_notification:
                await notify_admins_about_feedback(
                    bot=message.bot,
                    db_session=notification_session,
                    feedback=feedback_for_notification,
                    user=message.from_user
                )
                logger.info(f"✅ notify_admins_about_feedback завершена для feedback #{feedback_id}")
            else:
                logger.error(f"❌ Не удалось найти feedback #{feedback_id} для отправки уведомления")
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке уведомления админам о feedback #{feedback_id}: {e}", exc_info=True)
        # Не прерываем выполнение, даже если уведомление не отправилось
    
    await message.answer("Ваше сообщение сохранено, Мы ответим Вам в ближайшее время. Спасибо!")

# Обработчик для просмотра необработанных сообщений
@router.callback_query(lambda c: c.data == "view_feedback")
async def show_unprocessed_feedback(callback_query: types.CallbackQuery):
    logger.info("Обработчик 'Просмотреть сообщения' вызван.")
    async with get_session() as session:
        result = await session.execute(
            select(FeedbackMessage).where(FeedbackMessage.is_processed == False)
        )
        feedbacks = result.scalars().all()

    if not feedbacks:
        await callback_query.message.answer("Нет необработанных сообщений.")
        await callback_query.answer()
        return

    for feedback in feedbacks:
        # Подсчитываем количество ответов в рамках той же сессии
        replies_count = await session.scalar(
            select(func.count(FeedbackReply.id)).where(FeedbackReply.feedback_id == feedback.id)
        )
        feedback_text = (
            f"ID: {feedback.id}\n"
            f"Пользователь: @{feedback.username or 'Неизвестно'} (ID: {feedback.user_id})\n"
            f"Сообщение: {feedback.message}\n"
            f"Ответов: {replies_count}"
        )
        await callback_query.message.answer(feedback_text, reply_markup=get_feedback_keyboard(feedback.id))

    await callback_query.answer()

# Обработчик для пометки сообщения как обработанного
@router.callback_query(lambda c: c.data.startswith("mark_processed:"))
async def mark_feedback_processed(callback_query: types.CallbackQuery):
    logger.info(f"Callback 'mark_processed' вызван, user_id={callback_query.from_user.id}, data={callback_query.data}")
    feedback_id = int(callback_query.data.split(":")[1])

    async with get_session() as session:
        feedback = await session.get(FeedbackMessage, feedback_id)
        if not feedback:
            await callback_query.answer("Сообщение не найдено или уже обработано.", show_alert=True)
            return

        feedback.is_processed = True
        await session.commit()

    await callback_query.answer("Сообщение помечено как обработанное.", show_alert=True)
    await callback_query.message.delete()

# Обработчик для ответа на feedback
@router.message(StateFilter(FeedbackStates.awaiting_reply))
async def handle_feedback_reply(message: types.Message, state: FSMContext):
    data = await state.get_data()
    feedback_id = data.get("feedback_id")
    user_id = data.get("user_id")

    if not feedback_id or not user_id:
        await message.answer("Ошибка: невозможно найти данные для ответа.")
        await state.clear()
        return

    async with get_session() as session:
        feedback = await session.get(FeedbackMessage, feedback_id)
        if not feedback:
            await message.answer("Сообщение пользователя не найдено.")
            await state.clear()
            return

        try:
            # Создаем запись ответа в базе данных
            feedback_reply = FeedbackReply(
                feedback_id=feedback_id,
                admin_telegram_id=message.from_user.id,
                admin_username=message.from_user.username,
                reply_text=message.text,
                is_sent_to_user=False,
                sent_at=datetime.utcnow()  # Устанавливаем время отправки сразу
            )
            session.add(feedback_reply)
            
            # Отправляем сообщение пользователю
            await message.bot.send_message(
                chat_id=user_id,
                text=f"Ответ от администратора:\n\nВаше сообщение: {feedback.message}\n\nОтвет: {message.text}"
            )
            
            # Отмечаем ответ как отправленный
            feedback_reply.is_sent_to_user = True
            
            # Отмечаем сообщение как обработанное
            feedback.is_processed = True
            
            await session.commit()

            # Подтверждение администратору
            await message.answer(f"✅ Ответ успешно отправлен пользователю @{feedback.username}")

            # Удаляем сообщение с кнопками
            try:
                await message.bot.delete_message(
                    chat_id=message.chat.id,
                    message_id=message.message_id - 1
                )
            except Exception as e:
                logger.warning(f"Не удалось удалить сообщение с кнопками: {e}")

        except Exception as e:
            await message.answer(f"❌ Ошибка при отправке ответа: {str(e)}")
            logger.error(f"Ошибка отправки ответа: {e}")
        finally:
            await state.clear()

# Обработчик для начала ответа на сообщение
@router.callback_query(lambda c: c.data.startswith("reply_to_feedback:"))
async def start_feedback_reply(callback_query: types.CallbackQuery, state: FSMContext):
    logger.info(f"Callback 'reply_to_feedback' вызван, user_id={callback_query.from_user.id}, data={callback_query.data}")
    feedback_id = int(callback_query.data.split(":")[1])

    async with get_session() as session:
        feedback = await session.get(FeedbackMessage, feedback_id)
        if not feedback:
            await callback_query.answer("Сообщение не найдено.", show_alert=True)
            return

    # Сначала устанавливаем данные
    await state.update_data(feedback_id=feedback_id, user_id=feedback.user_id)
    # Затем устанавливаем состояние
    await state.set_state(FeedbackStates.awaiting_reply)

    await callback_query.message.answer(
        f"Введите ваш ответ для пользователя @{feedback.username}:\n"
        f"Исходное сообщение: {feedback.message}"
    )
    await callback_query.answer()

# Обработчик для удаления сообщения
@router.callback_query(lambda c: c.data.startswith("delete_feedback:"))
async def delete_feedback(callback_query: types.CallbackQuery):
    logger.info(f"Callback 'delete_feedback' вызван, user_id={callback_query.from_user.id}, data={callback_query.data}")
    feedback_id = int(callback_query.data.split(":")[1])

    async with get_session() as session:
        feedback = await session.get(FeedbackMessage, feedback_id)
        if not feedback:
            await callback_query.answer("Сообщение не найдено или уже удалено.", show_alert=True)
            return

        await session.delete(feedback)
        await session.commit()

    await callback_query.answer("Сообщение удалено.", show_alert=True)
    await callback_query.message.delete()

