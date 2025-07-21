"""
Сервис для управления админами через Telegram Bot API.
"""

import asyncio
import logging
import time
from typing import List, Optional, Tuple
from django.conf import settings
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

logger = logging.getLogger(__name__)


class TelegramAdminService:
    """
    Сервис для управления администраторами через Telegram Bot API.
    """
    
    def __init__(self, bot_token: str = None):
        """
        Инициализация сервиса.
        
        Args:
            bot_token (str): Токен бота. Если не указан, берется из настроек.
        """
        self.bot_token = bot_token or settings.TELEGRAM_BOT_TOKEN
        self.bot = Bot(token=self.bot_token)
    
    async def remove_admin_from_channel(self, chat_id: int, user_id: int) -> Tuple[bool, str]:
        """
        Удаляет администратора из канала/группы с учетом ограничений Telegram API.
        
        Args:
            chat_id (int): ID канала/группы
            user_id (int): Telegram ID пользователя
            
        Returns:
            Tuple[bool, str]: (успех, сообщение)
        """
        try:
            logger.info(f"Начинаем удаление администратора {user_id} из канала {chat_id}")
            
            # Сначала проверяем права бота
            bot_info = await self.bot.get_me()
            logger.info(f"Информация о боте: ID={bot_info.id}, username={bot_info.username}")
            
            bot_member = await self.bot.get_chat_member(chat_id=chat_id, user_id=bot_info.id)
            logger.info(f"Статус бота в канале: {bot_member.status}")
            logger.info(f"Права бота: can_promote_members={getattr(bot_member, 'can_promote_members', False)}")
            
            if bot_member.status != 'administrator':
                return False, f"❌ Бот не является администратором канала {chat_id}. Нужно добавить бота как администратора."
            
            if not getattr(bot_member, 'can_promote_members', False):
                return False, f"❌ У бота нет прав на управление администраторами в канале {chat_id}. Нужно дать боту право 'Добавлять администраторов'."
            
            # Проверяем текущий статус пользователя
            user_member = await self.bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            logger.info(f"Текущий статус пользователя {user_id}: {user_member.status}")
            
            if user_member.status != 'administrator':
                return False, f"❌ Пользователь {user_id} не является администратором канала {chat_id}"
            
            # Проверяем, является ли пользователь создателем
            if user_member.status == 'creator':
                return False, f"❌ Пользователь {user_id} является создателем канала {chat_id}. Нельзя удалить создателя."
            
            # Проверяем иерархию прав
            bot_can_restrict = getattr(bot_member, 'can_restrict_members', False)
            user_is_anonymous = getattr(user_member, 'is_anonymous', False)
            
            # Если пользователь анонимный, проверяем права бота
            if user_is_anonymous:
                if not bot_can_restrict:
                    return False, f"❌ Нельзя удалить анонимного администратора {user_id} из канала {chat_id}. У бота нет прав на ограничение участников."
            
            # Проверяем, кто назначал этого администратора
            # Если бот не назначал и у него нет прав на ограничение, то может не получиться
            if not bot_can_restrict:
                logger.warning(f"У бота нет прав на ограничение участников в канале {chat_id}")
            
            # Пытаемся удалить права администратора
            try:
                logger.info(f"Вызываем promote_chat_member для удаления прав администратора")
                await self.bot.promote_chat_member(
                    chat_id=chat_id,
                    user_id=user_id,
                    can_manage_chat=False,
                    can_delete_messages=False,
                    can_manage_video_chats=False,
                    can_restrict_members=False,
                    can_promote_members=False,
                    can_change_info=False,
                    can_invite_users=False,
                    can_post_stories=False,
                    can_edit_stories=False,
                    can_delete_stories=False,
                    can_post_messages=False,
                    can_edit_messages=False,
                    can_pin_messages=False,
                    can_manage_topics=False
                )
                
                logger.info(f"Администратор {user_id} успешно удален из канала {chat_id}")
                
                # Отправляем уведомление пользователю об удалении прав
                try:
                    # Получаем информацию о канале для уведомления
                    chat_info = await self.bot.get_chat(chat_id=chat_id)
                    channel_name = chat_info.title or f"канал {chat_id}"
                    
                    # Формируем ссылку на канал
                    if hasattr(chat_info, 'username') and chat_info.username:
                        channel_link = f"https://t.me/{chat_info.username}"
                        channel_display = f"<a href='{channel_link}'>{channel_name}</a>"
                    else:
                        channel_display = f"<b>{channel_name}</b>"
                    
                    notification_message = f"""
📢 <b>Уведомление</b>

Ваши права администратора были отозваны в канале {channel_display}

Вы больше не можете:
• Управлять сообщениями
• Удалять сообщения
• Приглашать пользователей
• Ограничивать участников
• Закреплять сообщения

Если у вас есть вопросы, обратитесь к владельцу канала.
                    """.strip()
                    
                    # Отправляем уведомление
                    await self.send_message_to_user(user_id, notification_message)
                    logger.info(f"Уведомление об удалении прав отправлено пользователю {user_id}")
                    
                except Exception as e:
                    logger.warning(f"Не удалось отправить уведомление пользователю {user_id}: {e}")
                
                return True, f"✅ Администратор {user_id} успешно удален из канала {chat_id}"
                
            except TelegramAPIError as promote_error:
                error_msg = str(promote_error)
                logger.error(f"Ошибка при удалении прав администратора: {error_msg}")
                
                # Обрабатываем специфические ошибки
                if "CHAT_ADMIN_REQUIRED" in error_msg:
                    # Дополнительная диагностика
                    try:
                        # Проверяем, кто является создателем канала
                        chat_info = await self.bot.get_chat(chat_id=chat_id)
                        creator_id = getattr(chat_info, 'id', None)
                        
                        # Проверяем, является ли пользователь создателем
                        if user_member.status == 'creator':
                            return False, f"❌ Пользователь {user_id} является создателем канала {chat_id}. Нельзя удалить создателя."
                        
                        # Проверяем иерархию прав более детально
                        bot_can_restrict = getattr(bot_member, 'can_restrict_members', False)
                        bot_can_promote = getattr(bot_member, 'can_promote_members', False)
                        
                        if not bot_can_promote:
                            return False, f"❌ У бота нет прав на управление администраторами в канале {chat_id}. Нужно дать боту право 'Добавлять администраторов'."
                        
                        if not bot_can_restrict:
                            return False, f"❌ У бота нет прав на ограничение участников в канале {chat_id}. Это может потребоваться для удаления администраторов."
                        
                        # Возможные причины ошибки
                        possible_reasons = []
                        if user_is_anonymous:
                            possible_reasons.append("пользователь является анонимным администратором")
                        
                        if creator_id and user_id == creator_id:
                            possible_reasons.append("пользователь является создателем канала")
                        
                        if not bot_can_restrict:
                            possible_reasons.append("у бота нет прав на ограничение участников")
                        
                        if possible_reasons:
                            reason_text = ", ".join(possible_reasons)
                            return False, f"❌ Нельзя удалить администратора {user_id} из канала {chat_id}. Возможные причины: {reason_text}"
                        else:
                            return False, f"❌ Нельзя удалить администратора {user_id} из канала {chat_id}. Возможно, администратор был назначен владельцем канала или имеет более высокий ранг."
                            
                    except Exception as diag_error:
                        logger.warning(f"Ошибка при диагностике: {diag_error}")
                        return False, f"❌ Нельзя удалить администратора {user_id} из канала {chat_id}. Бот не имеет достаточных прав или администратор имеет особый статус."
                elif "USER_NOT_PARTICIPANT" in error_msg:
                    return False, f"❌ Пользователь {user_id} не является участником канала {chat_id}."
                elif "USER_IS_ANONYMOUS" in error_msg:
                    return False, f"❌ Нельзя управлять анонимными администраторами в канале {chat_id}."
                elif "USER_IS_CREATOR" in error_msg:
                    return False, f"❌ Пользователь {user_id} является создателем канала {chat_id}. Нельзя удалить создателя."
                elif "ADMIN_RANK_TOO_HIGH" in error_msg:
                    return False, f"❌ Нельзя удалить администратора {user_id} из канала {chat_id}. У него более высокий ранг или равные права с ботом."
                elif "NOT_ENOUGH_RIGHTS" in error_msg:
                    return False, f"❌ У бота недостаточно прав для удаления администратора {user_id} из канала {chat_id}. Возможно, администратор был назначен владельцем канала."
                elif "USER_IS_OWNER" in error_msg:
                    return False, f"❌ Пользователь {user_id} является владельцем канала {chat_id}. Нельзя удалить владельца."
                else:
                    return False, f"❌ Ошибка Telegram API при удалении администратора {user_id} из канала {chat_id}: {error_msg}"
            
        except TelegramAPIError as e:
            error_msg = str(e)
            logger.error(f"Общая ошибка Telegram API: {error_msg}")
            
            if "CHAT_NOT_FOUND" in error_msg:
                return False, f"❌ Канал {chat_id} не найден или бот не имеет к нему доступа."
            elif "USER_NOT_FOUND" in error_msg:
                return False, f"❌ Пользователь {user_id} не найден в Telegram."
            elif "BOT_WAS_BLOCKED" in error_msg:
                return False, f"❌ Пользователь {user_id} заблокировал бота."
            elif "CHAT_WRITE_FORBIDDEN" in error_msg:
                return False, f"❌ Бот не может писать в канал {chat_id}."
            else:
                return False, f"❌ Неожиданная ошибка Telegram API при удалении администратора {user_id} из канала {chat_id}: {error_msg}"
        
        except Exception as e:
            error_msg = f"❌ Неожиданная ошибка при удалении администратора {user_id} из канала {chat_id}: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    async def remove_admin_from_all_channels(self, user_id: int, channel_ids: List[int]) -> Tuple[int, List[str]]:
        """
        Удаляет администратора из всех указанных каналов с детальным отчетом.
        
        Args:
            user_id (int): Telegram ID пользователя
            channel_ids (List[int]): Список ID каналов
            
        Returns:
            Tuple[int, List[str]]: (количество успешных удалений, список сообщений)
        """
        success_count = 0
        messages = []
        
        logger.info(f"Начинаем удаление администратора {user_id} из {len(channel_ids)} каналов")
        
        for i, chat_id in enumerate(channel_ids, 1):
            logger.info(f"Обрабатываем канал {i}/{len(channel_ids)}: {chat_id}")
            
            success, message = await self.remove_admin_from_channel(chat_id, user_id)
            if success:
                success_count += 1
                messages.append(f"✅ Канал {chat_id}: {message}")
            else:
                messages.append(f"❌ Канал {chat_id}: {message}")
        
        # Добавляем итоговое сообщение
        if success_count == len(channel_ids):
            messages.append(f"🎉 Администратор {user_id} успешно удален из всех {len(channel_ids)} каналов!")
        elif success_count > 0:
            messages.append(f"⚠️ Администратор {user_id} удален из {success_count}/{len(channel_ids)} каналов. Проверьте ошибки выше.")
        else:
            messages.append(f"❌ Не удалось удалить администратора {user_id} ни из одного канала. Проверьте права бота и статус администратора.")
        
        logger.info(f"Завершено удаление администратора {user_id}: {success_count}/{len(channel_ids)} успешно")
        return success_count, messages
    
    async def ban_user_from_channel(self, chat_id: int, user_id: int, until_date: Optional[int] = None) -> Tuple[bool, str]:
        """
        Ограничивает пользователя в канале/группе (применяет реальные ограничения).
        
        Args:
            chat_id (int): ID канала/группы
            user_id (int): Telegram ID пользователя
            until_date (Optional[int]): Дата разбана (Unix timestamp). По умолчанию 24 часа.
            
        Returns:
            Tuple[bool, str]: (успех, сообщение)
        """
        try:
            # Проверяем права бота
            bot_info = await self.bot.get_me()
            bot_member = await self.bot.get_chat_member(chat_id=chat_id, user_id=bot_info.id)
            
            if bot_member.status != 'administrator':
                return False, f"Бот не является администратором канала {chat_id}. Нужно добавить бота как администратора."
            
            # Проверяем права на ограничение
            if not getattr(bot_member, 'can_restrict_members', False):
                return False, f"У бота нет прав на ограничение участников в канале {chat_id}."
            
            # Получаем информацию о чате
            chat_info = await self.bot.get_chat(chat_id=chat_id)
            chat_type = chat_info.type
            
            # Проверяем статус пользователя
            user_member = await self.bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            logger.info(f"Статус пользователя {user_id} в {chat_type} {chat_id}: {user_member.status}")
            
            # Если пользователь является администратором, не баним
            if user_member.status == 'administrator':
                return False, f"Пользователь {user_id} является администратором {chat_type} {chat_id}. Нельзя ограничить администратора."
            
            # Если пользователь является создателем, не баним
            if user_member.status == 'creator':
                return False, f"Пользователь {user_id} является создателем {chat_type} {chat_id}. Нельзя ограничить создателя."
            
            # Если until_date не указан, устанавливаем 24 часа
            if until_date is None:
                until_date = int(time.time()) + (24 * 60 * 60)  # 24 часа
            
            # Применяем ограничения в зависимости от типа чата
            if chat_type == 'supergroup':
                # Для супергрупп используем restrict_chat_member
                try:
                    await self.bot.restrict_chat_member(
                        chat_id=chat_id,
                        user_id=user_id,
                        until_date=until_date,
                        permissions={
                            'can_send_messages': False,
                            'can_send_media_messages': False,
                            'can_send_other_messages': False,
                            'can_add_web_page_previews': False,
                            'can_send_polls': False,
                            'can_invite_users': False,
                            'can_pin_messages': False,
                            'can_change_info': False
                        }
                    )
                    logger.info(f"Пользователь {user_id} ограничен в супергруппе {chat_id}")
                except TelegramAPIError as e:
                    if "method is available only for supergroups" in str(e):
                        # Если это не супергруппа, просто логируем
                        logger.warning(f"Метод restrict_chat_member недоступен для {chat_type} {chat_id}")
                    else:
                        raise e
            elif chat_type == 'group':
                # Для обычных групп ограничения не работают, только удаление
                logger.warning(f"Ограничения недоступны для обычных групп. Пользователь {user_id} останется в группе {chat_id}")
            elif chat_type == 'channel':
                # Для каналов ограничения не работают, только удаление
                logger.warning(f"Ограничения недоступны для каналов. Пользователь {user_id} останется в канале {chat_id}")
            
            # Форматируем время разбана
            from datetime import datetime
            unban_time = datetime.fromtimestamp(until_date).strftime('%d.%m.%Y %H:%M')
            
            logger.info(f"Пользователь {user_id} заблокирован в {chat_type} {chat_id} до {unban_time}")
            return True, f"Пользователь {user_id} заблокирован в {chat_type} {chat_id} до {unban_time}"
            
        except TelegramAPIError as e:
            if "CHAT_ADMIN_REQUIRED" in str(e):
                error_msg = f"Бот не имеет прав администратора в канале {chat_id}. Добавьте бота как администратора."
            elif "USER_NOT_PARTICIPANT" in str(e):
                error_msg = f"Пользователь {user_id} не является участником канала {chat_id}."
            elif "USER_IS_ANONYMOUS" in str(e):
                error_msg = f"Нельзя ограничить анонимного администратора в канале {chat_id}."
            elif "method is available only for supergroups" in str(e):
                error_msg = f"Ограничения доступны только для супергрупп. Канал {chat_id} не является супергруппой."
            else:
                error_msg = f"Ошибка Telegram API при ограничении пользователя {user_id} в канале {chat_id}: {e}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Неожиданная ошибка при ограничении пользователя {user_id} в канале {chat_id}: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    async def unban_user_from_channel(self, chat_id: int, user_id: int) -> Tuple[bool, str]:
        """
        Снимает ограничения с пользователя в канале/группе.
        
        Args:
            chat_id (int): ID канала/группы
            user_id (int): Telegram ID пользователя
            
        Returns:
            Tuple[bool, str]: (успех, сообщение)
        """
        try:
            # Проверяем права бота
            bot_info = await self.bot.get_me()
            bot_member = await self.bot.get_chat_member(chat_id=chat_id, user_id=bot_info.id)
            
            if bot_member.status != 'administrator':
                return False, f"Бот не является администратором канала {chat_id}. Нужно добавить бота как администратора."
            
            # Проверяем права на ограничение
            if not getattr(bot_member, 'can_restrict_members', False):
                return False, f"У бота нет прав на ограничение участников в канале {chat_id}."
            
            # Получаем информацию о чате
            chat_info = await self.bot.get_chat(chat_id=chat_id)
            chat_type = chat_info.type
            
            # Снимаем ограничения в зависимости от типа чата
            if chat_type == 'supergroup':
                # Для супергрупп снимаем ограничения
                try:
                    await self.bot.restrict_chat_member(
                        chat_id=chat_id,
                        user_id=user_id,
                        until_date=0,  # Снимаем ограничения немедленно
                        permissions={
                            'can_send_messages': True,
                            'can_send_media_messages': True,
                            'can_send_other_messages': True,
                            'can_add_web_page_previews': True,
                            'can_send_polls': True,
                            'can_invite_users': True,
                            'can_pin_messages': True,
                            'can_change_info': True
                        }
                    )
                    logger.info(f"Ограничения сняты с пользователя {user_id} в супергруппе {chat_id}")
                except TelegramAPIError as e:
                    if "method is available only for supergroups" in str(e):
                        logger.warning(f"Метод restrict_chat_member недоступен для {chat_type} {chat_id}")
                    else:
                        raise e
            elif chat_type in ['group', 'channel']:
                logger.info(f"Ограничения автоматически сняты для {chat_type} {chat_id}")
            
            logger.info(f"Пользователь {user_id} разблокирован в {chat_type} {chat_id}")
            return True, f"Пользователь {user_id} разблокирован в {chat_type} {chat_id}"
            
        except TelegramAPIError as e:
            if "CHAT_ADMIN_REQUIRED" in str(e):
                error_msg = f"Бот не имеет прав администратора в канале {chat_id}. Добавьте бота как администратора."
            elif "USER_NOT_PARTICIPANT" in str(e):
                error_msg = f"Пользователь {user_id} не является участником канала {chat_id}."
            elif "method is available only for supergroups" in str(e):
                error_msg = f"Ограничения доступны только для супергрупп. Канал {chat_id} не является супергруппой."
            else:
                error_msg = f"Ошибка Telegram API при разблокировке пользователя {user_id} в канале {chat_id}: {e}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Неожиданная ошибка при разблокировке пользователя {user_id} в канале {chat_id}: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    async def remove_user_from_channel(self, chat_id: int, user_id: int) -> Tuple[bool, str]:
        """
        Полностью удаляет пользователя из канала/группы (кикает).
        
        Args:
            chat_id (int): ID канала/группы
            user_id (int): Telegram ID пользователя
            
        Returns:
            Tuple[bool, str]: (успех, сообщение)
        """
        try:
            # Сначала проверяем права бота
            bot_info = await self.bot.get_me()
            bot_member = await self.bot.get_chat_member(chat_id=chat_id, user_id=bot_info.id)
            
            logger.info(f"Проверяем права бота в канале {chat_id}. Статус: {bot_member.status}")
            
            if bot_member.status != 'administrator':
                return False, f"Бот не является администратором канала {chat_id}. Нужно добавить бота как администратора."
            
            logger.info(f"Права бота: can_promote_members={getattr(bot_member, 'can_promote_members', False)}, can_restrict_members={getattr(bot_member, 'can_restrict_members', False)}")
            
            if not getattr(bot_member, 'can_restrict_members', False):
                return False, f"У бота нет прав на удаление участников в канале {chat_id}."
            
            # Проверяем статус пользователя
            user_member = await self.bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            logger.info(f"Статус пользователя {user_id} в канале {chat_id}: {user_member.status}")
            
            # Если пользователь является администратором, сначала убираем права
            if user_member.status == 'administrator':
                logger.info(f"Пользователь {user_id} является администратором, пытаемся убрать права")
                
                if getattr(bot_member, 'can_promote_members', False):
                    # Убираем права администратора
                    logger.info(f"Пытаемся убрать права администратора у пользователя {user_id}")
                    try:
                        await self.bot.promote_chat_member(
                            chat_id=chat_id,
                            user_id=user_id,
                            can_manage_chat=False,
                            can_delete_messages=False,
                            can_manage_video_chats=False,
                            can_restrict_members=False,
                            can_promote_members=False,
                            can_change_info=False,
                            can_invite_users=False,
                            can_post_stories=False,
                            can_edit_stories=False,
                            can_delete_stories=False,
                            can_post_messages=False,
                            can_edit_messages=False,
                            can_pin_messages=False,
                            can_manage_topics=False
                        )
                        logger.info(f"Права администратора убраны у пользователя {user_id}")
                    except TelegramAPIError as promote_error:
                        logger.warning(f"Не удалось убрать права администратора: {promote_error}. Пытаемся удалить напрямую.")
                        # Продолжаем попытку удаления
                    except Exception as promote_error:
                        logger.error(f"Ошибка при убирании прав администратора: {promote_error}")
                        raise promote_error
                else:
                    logger.warning(f"У бота нет прав на управление администраторами в канале {chat_id}. Пытаемся удалить напрямую.")
            
            # Теперь удаляем пользователя из канала
            try:
                # Сначала пробуем разбанить (если пользователь был забанен ранее)
                await self.bot.unban_chat_member(
                    chat_id=chat_id,
                    user_id=user_id,
                    only_if_banned=True
                )
                logger.info(f"Пользователь {user_id} разбанен в канале {chat_id}")
            except Exception as unban_error:
                logger.info(f"Пользователь {user_id} не был забанен ранее: {unban_error}")
            
            # Теперь удаляем пользователя из канала
            await self.bot.ban_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                until_date=int(time.time()) + 30  # Бан на 30 секунд (эффективно кикает)
            )
            
            logger.info(f"Пользователь {user_id} удален из канала {chat_id}")
            return True, f"Пользователь {user_id} успешно удален из канала {chat_id}"
            
        except TelegramAPIError as e:
            if "CHAT_ADMIN_REQUIRED" in str(e):
                error_msg = f"Бот не имеет прав администратора в канале {chat_id}. Добавьте бота как администратора."
            elif "USER_NOT_PARTICIPANT" in str(e):
                error_msg = f"Пользователь {user_id} не является участником канала {chat_id}."
            elif "USER_IS_ANONYMOUS" in str(e):
                error_msg = f"Нельзя удалить анонимного администратора из канала {chat_id}."
            elif "user is an administrator" in str(e).lower():
                error_msg = f"Пользователь {user_id} все еще является администратором канала {chat_id}. Сначала нужно убрать права администратора."
            else:
                error_msg = f"Ошибка Telegram API при удалении пользователя {user_id} из канала {chat_id}: {e}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Неожиданная ошибка при удалении пользователя {user_id} из канала {chat_id}: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    async def remove_user_from_all_channels(self, user_id: int, channel_ids: List[int]) -> Tuple[int, List[str]]:
        """
        Удаляет пользователя из всех указанных каналов.
        
        Args:
            user_id (int): Telegram ID пользователя
            channel_ids (List[int]): Список ID каналов
            
        Returns:
            Tuple[int, List[str]]: (количество успешных удалений, список сообщений)
        """
        success_count = 0
        messages = []
        
        for chat_id in channel_ids:
            success, message = await self.remove_user_from_channel(chat_id, user_id)
            if success:
                success_count += 1
            messages.append(message)
        
        return success_count, messages
    
    async def get_chat_member(self, chat_id: int, user_id: int) -> Optional[dict]:
        """
        Получает информацию о участнике чата.
        
        Args:
            chat_id (int): ID канала/группы
            user_id (int): Telegram ID пользователя
            
        Returns:
            Optional[dict]: Информация о участнике или None
        """
        try:
            member = await self.bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            return {
                'status': member.status,
                'user': {
                    'id': member.user.id,
                    'username': member.user.username,
                    'first_name': member.user.first_name,
                    'last_name': member.user.last_name
                },
                'is_member': member.status in ['member', 'administrator', 'creator'],
                'is_admin': member.status == 'administrator',
                'is_creator': member.status == 'creator'
            }
        except TelegramAPIError as e:
            logger.error(f"Ошибка при получении информации о участнике {user_id} в канале {chat_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при получении информации о участнике {user_id} в канале {chat_id}: {e}")
            return None

    async def check_bot_permissions(self, chat_id: int) -> Tuple[bool, str]:
        """
        Проверяет права бота в канале/группе.
        
        Args:
            chat_id (int): ID канала/группы
            
        Returns:
            Tuple[bool, str]: (есть права, сообщение)
        """
        try:
            bot_info = await self.bot.get_me()
            bot_member = await self.bot.get_chat_member(chat_id=chat_id, user_id=bot_info.id)
            
            if bot_member.status != 'administrator':
                return False, f"Бот не является администратором канала {chat_id}"
            
            if not bot_member.can_promote_members:
                return False, f"У бота нет прав на управление администраторами в канале {chat_id}"
            
            return True, f"Бот имеет все необходимые права в канале {chat_id}"
            
        except TelegramAPIError as e:
            return False, f"Ошибка при проверке прав бота в канале {chat_id}: {e}"
        except Exception as e:
            return False, f"Неожиданная ошибка при проверке прав бота в канале {chat_id}: {e}"

    async def promote_user_to_admin(self, chat_id: int, user_id: int) -> Tuple[bool, str]:
        """
        Назначает пользователя администратором в канале/группе.
        
        Args:
            chat_id (int): ID канала/группы
            user_id (int): Telegram ID пользователя
            
        Returns:
            Tuple[bool, str]: (успех, сообщение)
        """
        try:
            logger.info(f"Начинаем назначение пользователя {user_id} администратором в канале {chat_id}")
            
            # Проверяем права бота
            bot_info = await self.bot.get_me()
            bot_member = await self.bot.get_chat_member(chat_id=chat_id, user_id=bot_info.id)
            
            if bot_member.status != 'administrator':
                return False, f"Бот не является администратором канала {chat_id}. Нужно добавить бота как администратора."
            
            if not bot_member.can_promote_members:
                return False, f"У бота нет прав на управление администраторами в канале {chat_id}."
            
            # Проверяем статус пользователя
            user_member = await self.bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            logger.info(f"Статус пользователя {user_id} в канале {chat_id}: {user_member.status}")
            
            if user_member.status not in ["member", "administrator", "creator"]:
                return False, f"Пользователь {user_id} не является участником канала {chat_id}"
            
            if user_member.status == "administrator":
                return False, f"Пользователь {user_id} уже является администратором канала {chat_id}"
            
            if user_member.status == "creator":
                return False, f"Пользователь {user_id} является создателем канала {chat_id}"
            
            # Назначаем администратора
            await self.bot.promote_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                can_manage_chat=True,
                can_post_messages=True,
                can_edit_messages=True,
                can_delete_messages=True,
                can_invite_users=True,
                can_restrict_members=True,
                can_pin_messages=True,
                can_promote_members=False  # Не даем права назначать других админов
            )
            
            # Проверяем, стал ли пользователь админом
            user_member_after = await self.bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            if user_member_after.status == "administrator":
                logger.info(f"Пользователь {user_id} успешно назначен администратором в канале {chat_id}")
                return True, f"Пользователь {user_id} успешно назначен администратором в канале {chat_id}"
            else:
                logger.warning(f"Пользователь {user_id} не стал администратором в канале {chat_id}, статус: {user_member_after.status}")
                return False, f"Не удалось назначить пользователя {user_id} администратором в канале {chat_id}"
            
        except TelegramAPIError as e:
            if "CHAT_ADMIN_REQUIRED" in str(e):
                error_msg = f"Бот не имеет прав администратора в канале {chat_id}. Добавьте бота как администратора."
            elif "USER_NOT_PARTICIPANT" in str(e):
                error_msg = f"Пользователь {user_id} не является участником канала {chat_id}."
            elif "USER_IS_ANONYMOUS" in str(e):
                error_msg = f"Нельзя назначать анонимных администраторов в канале {chat_id}."
            else:
                error_msg = f"Ошибка Telegram API при назначении администратора {user_id} в канале {chat_id}: {e}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Неожиданная ошибка при назначении администратора {user_id} в канале {chat_id}: {e}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg

    async def send_message_to_user(self, user_id: int, message: str) -> Tuple[bool, str]:
        """
        Отправляет сообщение пользователю в личку.
        
        Args:
            user_id (int): Telegram ID пользователя
            message (str): Текст сообщения
            
        Returns:
            Tuple[bool, str]: (успех, сообщение)
        """
        try:
            logger.info(f"Отправляем сообщение пользователю {user_id}: {message}")
            
            await self.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode='HTML'
            )
            
            logger.info(f"Сообщение успешно отправлено пользователю {user_id}")
            return True, f"Сообщение отправлено пользователю {user_id}"
            
        except TelegramAPIError as e:
            if "Forbidden" in str(e) and "bot was blocked" in str(e).lower():
                error_msg = f"Пользователь {user_id} заблокировал бота"
            elif "Forbidden" in str(e) and "user is deactivated" in str(e).lower():
                error_msg = f"Пользователь {user_id} деактивирован"
            elif "Bad Request" in str(e) and "chat not found" in str(e).lower():
                error_msg = f"Пользователь {user_id} не найден"
            else:
                error_msg = f"Ошибка Telegram API при отправке сообщения пользователю {user_id}: {e}"
            logger.warning(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Неожиданная ошибка при отправке сообщения пользователю {user_id}: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def close(self):
        """
        Закрывает соединение с ботом.
        """
        if self.bot:
            try:
                # Пытаемся получить текущий event loop
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_closed():
                        # Если loop закрыт, создаем новый
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                except RuntimeError:
                    # Если нет текущего loop, создаем новый
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                # Закрываем сессию бота
                loop.run_until_complete(self.bot.session.close())
                
            except Exception as e:
                logger.warning(f"Ошибка при закрытии сессии бота: {e}")


def run_async_function(func, *args, **kwargs):
    """
    Запускает асинхронную функцию в синхронном контексте.
    
    Args:
        func: Асинхронная функция
        *args: Аргументы функции
        **kwargs: Именованные аргументы функции
        
    Returns:
        Результат выполнения функции
    """
    try:
        # Пытаемся получить текущий event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                # Если loop закрыт, создаем новый
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            # Если нет текущего loop, создаем новый
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Запускаем функцию
        return loop.run_until_complete(func(*args, **kwargs))
        
    except Exception as e:
        logger.error(f"Ошибка в run_async_function: {e}")
        raise e 