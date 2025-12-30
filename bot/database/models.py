import uuid
from datetime import datetime

from sqlalchemy import Column, Integer, String, JSON, ForeignKey, Boolean, DateTime, BigInteger, UniqueConstraint, func, \
    Table, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from bot.database.database import Base
import logging



logger = logging.getLogger(__name__)




# Промежуточная таблица для связи TelegramAdmin и TelegramGroup
telegramadmin_groups = Table(
    'telegramadmin_groups',
    Base.metadata,
    Column('telegram_admin_id', Integer, ForeignKey('telegram_admins.id'), primary_key=True),
    Column('telegram_group_id', BigInteger, ForeignKey('telegram_groups.group_id'), primary_key=True)
)



class TelegramAdmin(Base):
    """
    Модель администратора Telegram-бота, синхронизированная с Django таблицей admins.
    """
    __tablename__ = 'telegram_admins'

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    photo = Column(String(500), nullable=True)
    language = Column(String(10), default='en', nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # ManyToMany с TelegramGroup через промежуточную таблицу
    groups = relationship(
        "TelegramGroup",
        secondary=telegramadmin_groups,
        back_populates="admins"
    )





class TelegramGroup(Base):
    """
    Модель для хранения информации о Telegram-группах или каналах.

    Attributes:
        id (int): Уникальный идентификатор группы/канала.
        group_name (str): Название группы/канала.
        group_id (int): Telegram ID группы/канала (уникальный).
        topic_id (int): ID связанной темы (ForeignKey к таблице topics).
        language (str): Язык группы/канала.
        location_type (str): Тип (группа, канал или веб-сайт).
        username (str, optional): Username группы/канала (например, '@ChannelName').
        user_subscriptions: Связь с подписками пользователей.
        tasks: Связь с задачами, связанными с группой/каналом.
    """
    __tablename__ = 'telegram_groups'

    id = Column(Integer, primary_key=True)
    group_name = Column(String, nullable=False)
    group_id = Column(BigInteger, unique=True, nullable=False)
    topic_id = Column(Integer, ForeignKey('topics.id'), nullable=False)
    language = Column(String, nullable=False)
    location_type = Column(String, nullable=False, default="group")
    username = Column(String, nullable=True)

    user_subscriptions = relationship(
        "UserChannelSubscription",
        back_populates="channel",
        cascade="all, delete-orphan"
    )
    tasks = relationship('Task', back_populates='group')
    admins = relationship(
        "TelegramAdmin",
        secondary=telegramadmin_groups,
        back_populates="groups"
    )

    def __str__(self):
        return self.group_name




class Task(Base):
    __tablename__ = 'tasks'

    id = Column(Integer, primary_key=True)
    topic_id = Column(Integer, ForeignKey('topics.id'), nullable=False)
    subtopic_id = Column(Integer, ForeignKey('subtopics.id'), nullable=True)
    difficulty = Column(String, nullable=False)
    published = Column(Boolean, default=False, nullable=False)
    create_date = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    publish_date = Column(DateTime(timezone=True), nullable=True)
    image_url = Column(String, nullable=True)
    external_link = Column(String, nullable=True)
    video_url = Column(String, nullable=True)
    # Совместимость с Django: в БД есть not null JSONB поле video_urls со значением по умолчанию {}
    video_urls = Column(JSON, nullable=False, default=dict)
    # Совместимость с Django: not null JSONB для прогресса генерации видео
    video_generation_progress = Column(JSON, nullable=False, default=dict)
    translation_group_id = Column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False)
    error = Column(Boolean, default=False)
    message_id = Column(Integer, unique=False, nullable=True)
    group_id = Column(BigInteger, ForeignKey('telegram_groups.id'), nullable=True)

    translations = relationship('TaskTranslation', back_populates='task', cascade="all, delete-orphan")
    statistics = relationship('TaskStatistics', back_populates='task', cascade="all, delete-orphan")
    group = relationship('TelegramGroup', back_populates='tasks')
    polls = relationship('TaskPoll', back_populates='task', cascade="all, delete-orphan")
    topic = relationship('Topic', back_populates='tasks')
    subtopic = relationship('Subtopic', back_populates='tasks')



class TaskTranslation(Base):
    __tablename__ = 'task_translations'

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey('tasks.id', ondelete='CASCADE'), nullable=False)
    language = Column(String, nullable=False)
    question = Column(String, nullable=False)
    answers = Column(JSON, nullable=False)
    correct_answer = Column(String, nullable=False)
    explanation = Column(String, nullable=True)
    # Совместимость с Django: длинное объяснение для сайта
    long_explanation = Column(String, nullable=True)
    publish_date = Column(DateTime(timezone=True), nullable=True)

    task = relationship('Task', back_populates='translations')




class TelegramUser(Base):
    """
    Модель пользователя Telegram-бота, хранит данные о пользователях и их подписках.
    """
    __tablename__ = 'telegram_users'

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    subscription_status = Column(String(20), default='inactive', nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False)
    language = Column(String(10), nullable=True)
    deactivated_at = Column(DateTime, nullable=True)
    is_premium = Column(Boolean, default=False, nullable=False)
    linked_user_id = Column(BigInteger, nullable=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        logger.debug(f"Создаём TelegramUser с created_at={self.created_at}")  # ДОБАВИТЬ: Отладка

    channel_subscriptions = relationship(
        "UserChannelSubscription",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    statistics = relationship(
        "TaskStatistics",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<TelegramUser(id={self.id}, telegram_id={self.telegram_id}, status={self.subscription_status})>"



class TaskStatistics(Base):
    __tablename__ = 'task_statistics'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('telegram_users.id'), nullable=False)
    task_id = Column(Integer, ForeignKey('tasks.id'), nullable=False)
    attempts = Column(Integer, default=0, nullable=False)
    successful = Column(Boolean, default=False, nullable=False)
    last_attempt_date = Column(DateTime(timezone=True), nullable=True)

    user = relationship('TelegramUser', back_populates='statistics')
    task = relationship('Task', back_populates='statistics')





class Topic(Base):
    __tablename__ = 'topics'

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    icon = Column(String, nullable=True, default='/static/blog/images/icons/default-icon.png')
    description = Column(String, nullable=True)

    tasks = relationship('Task', back_populates='topic')

class Subtopic(Base):
    __tablename__ = 'subtopics'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    topic_id = Column(Integer, ForeignKey('topics.id'), nullable=False)

    tasks = relationship('Task', back_populates='subtopic')

class TaskPoll(Base):
    __tablename__ = 'task_polls'

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey('tasks.id'), nullable=False)
    translation_id = Column(Integer, ForeignKey('task_translations.id'), nullable=False)
    poll_id = Column(String, nullable=False, unique=True)
    poll_question = Column(String, nullable=True)
    poll_options = Column(JSON, nullable=True)
    is_anonymous = Column(Boolean, default=True)
    poll_type = Column(String, nullable=True)
    allows_multiple_answers = Column(Boolean, default=False)
    total_voter_count = Column(Integer, default=0)
    poll_link = Column(String, nullable=True)

    task = relationship('Task', back_populates='polls')
    translation = relationship('TaskTranslation')

class Webhook(Base):
    __tablename__ = 'webhooks'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url = Column(String, nullable=False, unique=True)
    service_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=True)

class DefaultLink(Base):
    __tablename__ = 'default_links'

    id = Column(Integer, primary_key=True, index=True)
    language = Column(String, nullable=False)
    topic = Column(String, nullable=False)
    link = Column(String, nullable=False)

    __table_args__ = (
        UniqueConstraint('language', 'topic', name='uix_language_topic'),
    )





class UserChannelSubscription(Base):
    """
    Модель подписки пользователя на Telegram-канал или группу.
    Хранит связь между TelegramUser и каналом.
    Синхронизирована с Django-моделью UserChannelSubscription.
    """
    __tablename__ = 'user_channel_subscriptions'

    id = Column(Integer, primary_key=True)
    telegram_user_id = Column(Integer, ForeignKey('telegram_users.id'), nullable=False)
    channel_id = Column(BigInteger, ForeignKey('telegram_groups.group_id'), nullable=False)
    subscription_status = Column(String(20), default='inactive', nullable=False)
    subscribed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    unsubscribed_at = Column(TIMESTAMP(timezone=True), nullable=True)

    user = relationship('TelegramUser', back_populates='channel_subscriptions')
    channel = relationship('TelegramGroup', back_populates='user_subscriptions')

    def __repr__(self):
        return f"<UserChannelSubscription(telegram_user_id={self.telegram_user_id}, channel_id={self.channel_id}, status={self.subscription_status})>"







class MainFallbackLink(Base):
    __tablename__ = 'main_fallback_links'

    id = Column(Integer, primary_key=True, index=True)
    language = Column(String, nullable=False)
    link = Column(String, nullable=False)

    __table_args__ = (
        UniqueConstraint('language', name='uix_language'),
    )

    def __repr__(self):
        return f"<MainFallbackLink(language={self.language}, link={self.link})>"


class GlobalWebhookLink(Base):
    """
    Модель для хранения глобальных ссылок, которые добавляются в вебхуки.
    Синхронизирована с Django моделью GlobalWebhookLink.
    """
    __tablename__ = 'global_webhook_links'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    url = Column(String(500), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    def __repr__(self):
        return f"<GlobalWebhookLink(name={self.name}, url={self.url}, is_active={self.is_active})>"


class FeedbackMessage(Base):
    __tablename__ = 'feedback_messages'

    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, nullable=False)
    username = Column(String, nullable=True)
    message = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    is_processed = Column(Boolean, default=False)
    source = Column(String(20), nullable=True, default='bot')  # Источник: bot или mini_app
    category = Column(String(20), nullable=True, default='other')  # Категория: bug, suggestion, complaint, other

    # Связь с ответами
    replies = relationship('FeedbackReply', back_populates='feedback', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<FeedbackMessage(user_id={self.user_id}, username={self.username}, message={self.message[:20]})>"


class FeedbackReply(Base):
    """
    Модель для хранения ответов администраторов на сообщения поддержки.
    """
    __tablename__ = 'feedback_replies'

    id = Column(Integer, primary_key=True)
    feedback_id = Column(Integer, ForeignKey('feedback_messages.id'), nullable=False)
    admin_id = Column(Integer, nullable=True)  # ForeignKey к Django User (может быть null)
    admin_telegram_id = Column(BigInteger, nullable=False)
    admin_username = Column(String, nullable=True)
    reply_text = Column(String, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    is_sent_to_user = Column(Boolean, default=False)
    sent_at = Column(DateTime, nullable=True)
    send_error = Column(String, nullable=True)

    # Связь с сообщением
    feedback = relationship('FeedbackMessage', back_populates='replies')

    def __repr__(self):
        return f"<FeedbackReply(feedback_id={self.feedback_id}, admin_telegram_id={self.admin_telegram_id}, reply_text={self.reply_text[:20]})>"