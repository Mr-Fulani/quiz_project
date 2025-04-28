import uuid
from datetime import datetime

from sqlalchemy import Column, Integer, String, JSON, ForeignKey, Boolean, DateTime, BigInteger, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from bot.utils.time import get_current_time
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
    date_joined = Column(DateTime, server_default=func.now(), nullable=False)

    # Добавляем поле, соответствующее Django-полю `is_super_admin`:
    is_super_admin = Column(Boolean, default=False, nullable=False)

    def __repr__(self):
        return f"<Admin(username={self.username}, telegram_id={self.telegram_id})>"



    @property
    def photo_url(self):
        """
        Возвращает ссылку на фото администратора или ссылку на фото по умолчанию.
        """
        return self.photo or "/static/images/default_avatar.png"

    def __repr__(self):
        return f"<Admin(username={self.username}, telegram_id={self.telegram_id}, language={self.language})>"




# Модель задач
class Task(Base):
    __tablename__ = 'tasks'

    id = Column(Integer, primary_key=True)
    topic_id = Column(Integer, ForeignKey('topics.id'), nullable=False)  # Связь с темой
    subtopic_id = Column(Integer, ForeignKey('subtopics.id'), nullable=True)  # Связь с подтемой
    difficulty = Column(String, nullable=False)  # Сложность задачи
    published = Column(Boolean, default=False, nullable=False)  # Статус публикации
    create_date = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)  # Дата создания задачи
    publish_date = Column(DateTime(timezone=True), nullable=True)  # Дата публикации

    # Поле для ссылки на картинку из S3
    image_url = Column(String, nullable=True)

    # Новое поле для ссылки на сторонний ресурс (например, Telegram канал)
    external_link = Column(String, nullable=True)
    translation_group_id = Column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False)
    error = Column(Boolean, default=False)  # Поле для пометки задач с ошибками

    message_id = Column(Integer, unique=False, nullable=True)
    # Связь с таблицей переводов задач
    translations = relationship('TaskTranslation', back_populates='task', cascade="all, delete-orphan")
    # Связь с таблицей статистики
    statistics = relationship('TaskStatistics', back_populates='task', cascade="all, delete-orphan")
    # Связь с таблицей групп
    group_id = Column(BigInteger, ForeignKey('groups.id'), nullable=True)  # Ссылка на группу
    group = relationship('Group', back_populates='tasks')

    # Связь с опросом
    polls = relationship('TaskPoll', back_populates='task', cascade="all, delete-orphan")

    # Связь с темой
    topic = relationship('Topic', back_populates='tasks')
    # Связь с подтемой
    subtopic = relationship('Subtopic', back_populates='tasks')


# Модель переводов задач
class TaskTranslation(Base):
    __tablename__ = 'task_translations'

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey('tasks.id', ondelete='CASCADE'), nullable=False)  # Связь с задачей
    language = Column(String, nullable=False)  # Язык перевода
    question = Column(String, nullable=False)  # Вопрос
    answers = Column(JSON, nullable=False)  # Варианты ответов
    correct_answer = Column(String, nullable=False)  # Правильный ответ
    explanation = Column(String, nullable=True)  # Объяснение ответа
    publish_date = Column(DateTime(timezone=True), nullable=True)

    # Обратная связь с задачей
    task = relationship('Task', back_populates='translations')


# Модель пользователей
class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)  # Telegram ID пользователя
    username = Column(String, nullable=True)  # Имя пользователя
    subscription_status = Column(String, default='inactive', nullable=False)  # Статус подписки
    created_at = Column(DateTime, default=get_current_time, nullable=False)  # Дата создания
    language = Column(String, nullable=True)  # Язык пользователя
    password = Column(String, nullable=False, default="passforuser")  # Пароль пользователя

    date_joined = Column(DateTime, server_default=func.now(), nullable=False)
    deactivated_at = Column(DateTime, nullable=True)

    is_superuser = Column(Boolean, nullable=False)
    is_staff = Column(Boolean, nullable=False)
    is_active = Column(Boolean, nullable=False)


    channel_subscriptions = relationship(
        "UserChannelSubscription",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    # Связь с таблицей статистики задач
    statistics = relationship('TaskStatistics', back_populates='user', cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User id={self.id}, tg_id={self.telegram_id}, status={self.subscription_status}>"


# Модель статистики задач
class TaskStatistics(Base):
    __tablename__ = 'task_statistics'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)  # Связь с пользователем
    task_id = Column(Integer, ForeignKey('tasks.id'), nullable=False)  # Связь с задачей
    attempts = Column(Integer, default=0, nullable=False)  # Количество попыток
    successful = Column(Boolean, default=False, nullable=False)  # Успешность
    last_attempt_date = Column(DateTime(timezone=True), nullable=True)  # Дата последней попытки

    # Обратная связь с пользователем
    user = relationship('User', back_populates='statistics')
    # Обратная связь с задачей
    task = relationship('Task', back_populates='statistics')


# Модель групп
class Group(Base):
    __tablename__ = 'groups'

    id = Column(Integer, primary_key=True)
    group_name = Column(String, nullable=False)  # Имя группы
    group_id = Column(BigInteger, unique=True, nullable=False)  # Telegram ID группы
    topic_id = Column(Integer, ForeignKey('topics.id'), nullable=False)  # Связь с темой
    language = Column(String, nullable=False)  # Язык группы
    location_type = Column(String, nullable=False, default="group")  # Тип: "group" или "channel"
    username = Column(String, nullable=True)

    # Дополнительно:
    user_subscriptions = relationship(
        "UserChannelSubscription",
        back_populates="channel",
        cascade="all, delete-orphan"
    )

    # Связь с задачами
    tasks = relationship('Task', back_populates='group')


# Модель тем
class Topic(Base):
    __tablename__ = 'topics'

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)  # Название темы (Python, Golang и т.д.)
    icon = Column(String, nullable=True, default='/static/blog/images/icons/default-icon.png')  # Путь к иконке темы
    description = Column(String, nullable=True)  # Описание темы

    # Связь с задачами
    tasks = relationship('Task', back_populates='topic')


# Модель подтем
class Subtopic(Base):
    __tablename__ = 'subtopics'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)  # Название подтемы
    topic_id = Column(Integer, ForeignKey('topics.id'), nullable=False)  # Связь с темой

    # Связь с задачами
    tasks = relationship('Task', back_populates='subtopic')





class TaskPoll(Base):
    __tablename__ = 'task_polls'

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey('tasks.id'), nullable=False)  # Связь с задачей
    translation_id = Column(Integer, ForeignKey('task_translations.id'), nullable=False)  # Связь с переводом
    poll_id = Column(String, nullable=False, unique=True)  # Telegram poll_id
    poll_question = Column(String, nullable=True)
    poll_options = Column(JSON, nullable=True)  # Список опций
    is_anonymous = Column(Boolean, default=True)
    poll_type = Column(String, nullable=True)
    allows_multiple_answers = Column(Boolean, default=False)
    total_voter_count = Column(Integer, default=0)
    poll_link = Column(String, nullable=True)

    # Связи
    task = relationship('Task', back_populates='polls')
    translation = relationship('TaskTranslation')






class Webhook(Base):
    __tablename__ = 'webhooks'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url = Column(String, nullable=False, unique=True)
    service_name = Column(String, nullable=True)  # Например, make.com, Zapier и т.д.
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
    Промежуточная таблица, показывающая, на каких каналах/группах
    пользователь (User) подписан или нет.
    """
    __tablename__ = 'user_channel_subscriptions'

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    channel_id = Column(BigInteger, ForeignKey('groups.group_id'), nullable=False)
    #  ^ channel_id (или group_id) — это Telegram ID канала/группы

    # subscription_status: 'active' (подписался) или 'inactive' (отписался)
    subscription_status = Column(String, default='inactive', nullable=False)

    subscribed_at = Column(DateTime, nullable=True)
    unsubscribed_at = Column(DateTime, nullable=True)

    # Связи (по желанию, если нужно ORM-связь)
    user = relationship('User', back_populates='channel_subscriptions')
    channel = relationship('Group', back_populates='user_subscriptions')

    def __repr__(self):
        return (f"<UserChannelSubscription user_id={self.user_id}, "
                f"channel_id={self.channel_id}, status={self.subscription_status}>")




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
    user_id = Column(BigInteger, nullable=False)  # Telegram ID пользователя
    username = Column(String, nullable=True)  # Имя пользователя
    message = Column(String, nullable=False)  # Текст сообщения
    created_at = Column(DateTime, server_default=func.now(), nullable=False)  # Дата создания
    is_processed = Column(Boolean, default=False)  # Статус обработки (обработано или нет)

    def __repr__(self):
        return f"<FeedbackMessage(user_id={self.user_id}, username={self.username}, message={self.message[:20]})>"



