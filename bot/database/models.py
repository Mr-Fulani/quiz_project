import uuid
from datetime import datetime

from sqlalchemy import Column, Integer, String, JSON, ForeignKey, Boolean, DateTime, BigInteger, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from bot.database.database import Base



class Admin(Base):
    __tablename__ = 'admins'

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    photo = Column(String, nullable=True)
    language = Column(String(10), default='ru', nullable=False)
    phone_number = Column(String(15), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    password = Column(String(128), nullable=False)
    email = Column(String(255), default='', nullable=False)
    is_django_admin = Column(Boolean, default=False, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    is_staff = Column(Boolean, default=False, nullable=False)
    is_super_admin = Column(Boolean, default=False, nullable=False)
    date_joined = Column(DateTime, server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<Admin(username={self.username}, telegram_id={self.telegram_id}, language={self.language})>"

    @property
    def photo_url(self):
        return self.photo or "/static/images/default_avatar.png"

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
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    language = Column(String(10), nullable=True)
    deactivated_at = Column(DateTime, nullable=True)

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

    def __str__(self):
        """
        Строковое представление объекта TelegramGroup.

        Returns:
            str: Название группы/канала.
        """
        return self.group_name



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
    Промежуточная таблица для связи пользователей и каналов/групп.
    """
    __tablename__ = 'user_channel_subscriptions'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('telegram_users.id'), nullable=False)
    channel_id = Column(BigInteger, ForeignKey('telegram_groups.group_id'), nullable=False)
    subscription_status = Column(String, default='inactive', nullable=False)
    subscribed_at = Column(DateTime, nullable=True)
    unsubscribed_at = Column(DateTime, nullable=True)

    user = relationship('TelegramUser', back_populates='channel_subscriptions')
    channel = relationship('TelegramGroup', back_populates='user_subscriptions')

    def __repr__(self):
        return f"<UserChannelSubscription(user_id={self.user_id}, channel_id={self.channel_id}, status={self.subscription_status})>"

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

class FeedbackMessage(Base):
    __tablename__ = 'feedback_messages'

    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, nullable=False)
    username = Column(String, nullable=True)
    message = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    is_processed = Column(Boolean, default=False)

    def __repr__(self):
        return f"<FeedbackMessage(user_id={self.user_id}, username={self.username}, message={self.message[:20]})>"