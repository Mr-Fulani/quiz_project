import uuid
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Column, Integer, String, JSON, ForeignKey, Boolean, DateTime, BigInteger
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from database.database import Base

def get_current_time():
    return datetime.now(timezone.utc)

# Модель администраторов
class Admin(Base):
    __tablename__ = 'admins'

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)  # Telegram ID администратора
    username = Column(String, nullable=True)  # Имя пользователя (опционально)

# Модель задач
class Task(Base):
    __tablename__ = 'tasks'

    id = Column(Integer, primary_key=True)
    topic_id = Column(Integer, ForeignKey('topics.id'), nullable=False)  # Связь с темой
    subtopic_id = Column(Integer, ForeignKey('subtopics.id'), nullable=True)  # Связь с подтемой
    difficulty = Column(String, nullable=False)  # Сложность задачи
    published = Column(Boolean, default=False, nullable=False)  # Статус публикации
    create_date = Column(DateTime, default=datetime.utcnow, nullable=False)  # Дата создания задачи
    publish_date = Column(DateTime, nullable=True)  # Дата публикации

    # Поле для ссылки на картинку из S3
    image_url = Column(String, nullable=True)

    # Новое поле для ссылки на сторонний ресурс (например, Telegram канал)
    external_link = Column(String, default="https://t.me/tyt_python", nullable=True)
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
    poll = relationship('TaskPoll', back_populates='task', uselist=False)

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

    # Обратная связь с задачей
    task = relationship('Task', back_populates='translations')

# Модель пользователей
class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)  # Telegram ID пользователя
    username = Column(String, nullable=True)  # Имя пользователя
    subscription_status = Column(String, default='inactive', nullable=False)  # Статус подписки
    created_at = Column(DateTime, default=get_current_time, nullable=False)  # Дата создания
    language = Column(String, nullable=True)  # Язык пользователя

    # Связь с таблицей статистики задач
    statistics = relationship('TaskStatistics', back_populates='user', cascade="all, delete-orphan")

# Модель статистики задач
class TaskStatistics(Base):
    __tablename__ = 'task_statistics'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)  # Связь с пользователем
    task_id = Column(Integer, ForeignKey('tasks.id'), nullable=False)  # Связь с задачей
    attempts = Column(Integer, default=0, nullable=False)  # Количество попыток
    successful = Column(Boolean, default=False, nullable=False)  # Успешность
    last_attempt_date = Column(DateTime, nullable=True)  # Дата последней попытки

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

    # Связь с задачами
    tasks = relationship('Task', back_populates='group')

# Модель тем
class Topic(Base):
    __tablename__ = 'topics'

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)  # Название темы (Python, Golang и т.д.)
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
    task_id = Column(Integer, ForeignKey('tasks.id'), nullable=False, unique=True)  # Связь с задачей
    poll_id = Column(String, nullable=True)
    poll_question = Column(String, nullable=True)
    poll_options = Column(JSON, nullable=True)  # Список опций
    is_anonymous = Column(Boolean, default=True)
    poll_type = Column(String, nullable=True)
    allows_multiple_answers = Column(Boolean, default=False)
    total_voter_count = Column(Integer, default=0)
    poll_link = Column(String, nullable=True)

    # Обратная связь с задачей
    task = relationship('Task', back_populates='poll')




