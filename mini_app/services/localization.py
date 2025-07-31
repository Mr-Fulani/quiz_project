"""
Сервис локализации для мини-приложения
"""
from typing import Dict, Any, Optional
from core.config import settings

class LocalizationService:
    """Сервис для управления переводами в мини-приложении"""
    
    # Словари переводов
    TRANSLATIONS = {
        "en": {
            # Навигация
            "home": "Home",
            "profile": "Profile", 
            "achievements": "Achievements",
            "statistics": "Statistics",
            "settings": "Settings",
            
            # Главная страница
            "search_placeholder": "Search topics...",
            "start_button": "Start",
            "back_button": "Back",
            "questions_count": "questions",
            "difficulty_easy": "Easy",
            "difficulty_medium": "Medium", 
            "difficulty_hard": "Hard",
            
            # Задачи
            "tasks": "Tasks",
            "task_image": "Task Image",
            "explanation": "Explanation",
            "no_tasks_available": "No tasks available",
            "correct_answer": "Correct Answer",
            "incorrect_answer": "Incorrect Answer",
            
            # Профиль
            "profile_title": "Profile",
            "edit_profile": "Edit Profile",
            "save_changes": "Save Changes",
            "cancel": "Cancel",
            "upload_avatar": "Upload Avatar",
            "username": "Username",
            "first_name": "First Name",
            "last_name": "Last Name",
            "language": "Language",
            
            # Достижения
            "achievements_title": "Achievements",
            "no_achievements": "No achievements yet",
            "keep_learning": "Keep learning to unlock achievements!",
            
            # Статистика
            "statistics_title": "Statistics",
            "total_questions": "Total Questions",
            "correct_answers": "Correct Answers",
            "accuracy": "Accuracy",
            "streak": "Current Streak",
            "best_streak": "Best Streak",
            
            # Настройки
            "settings_title": "Settings",
            "language_settings": "Language",
            "notifications": "Notifications",
            "dark_mode": "Dark Mode",
            "about": "About",
            "version": "Version",
            
            # Общие
            "loading": "Loading...",
            "error": "Error",
            "success": "Success",
            "confirm": "Confirm",
            "delete": "Delete",
            "edit": "Edit",
            "close": "Close",
        },
        "ru": {
            # Навигация
            "home": "Главная",
            "profile": "Профиль",
            "achievements": "Достижения", 
            "statistics": "Статистика",
            "settings": "Настройки",
            
            # Главная страница
            "search_placeholder": "Поиск тем...",
            "start_button": "Начать",
            "back_button": "Назад",
            "questions_count": "вопросов",
            "difficulty_easy": "Легкий",
            "difficulty_medium": "Средний",
            "difficulty_hard": "Сложный",
            
            # Задачи
            "tasks": "Задачи",
            "task_image": "Изображение задачи",
            "explanation": "Объяснение",
            "no_tasks_available": "Задачи не найдены",
            "correct_answer": "Правильный ответ",
            "incorrect_answer": "Неправильный ответ",
            
            # Профиль
            "profile_title": "Профиль",
            "edit_profile": "Редактировать профиль",
            "save_changes": "Сохранить изменения",
            "cancel": "Отмена",
            "upload_avatar": "Загрузить аватар",
            "username": "Имя пользователя",
            "first_name": "Имя",
            "last_name": "Фамилия",
            "language": "Язык",
            
            # Достижения
            "achievements_title": "Достижения",
            "no_achievements": "Пока нет достижений",
            "keep_learning": "Продолжайте учиться, чтобы открыть достижения!",
            
            # Статистика
            "statistics_title": "Статистика",
            "total_questions": "Всего вопросов",
            "correct_answers": "Правильных ответов",
            "accuracy": "Точность",
            "streak": "Текущая серия",
            "best_streak": "Лучшая серия",
            
            # Настройки
            "settings_title": "Настройки",
            "language_settings": "Язык",
            "notifications": "Уведомления",
            "dark_mode": "Темная тема",
            "about": "О приложении",
            "version": "Версия",
            
            # Общие
            "loading": "Загрузка...",
            "error": "Ошибка",
            "success": "Успешно",
            "confirm": "Подтвердить",
            "delete": "Удалить",
            "edit": "Редактировать",
            "close": "Закрыть",
        }
    }
    
    def __init__(self, default_language: str = None):
        self.default_language = default_language or settings.DEFAULT_LANGUAGE
        self.current_language = self.default_language
    
    def set_language(self, language: str) -> bool:
        """Устанавливает текущий язык"""
        if language in settings.SUPPORTED_LANGUAGES:
            self.current_language = language
            return True
        return False
    
    def get_language(self) -> str:
        """Возвращает текущий язык"""
        return self.current_language
    
    def get_text(self, key: str, language: str = None) -> str:
        """Получает перевод по ключу"""
        lang = language or self.current_language
        translations = self.TRANSLATIONS.get(lang, self.TRANSLATIONS[settings.DEFAULT_LANGUAGE])
        return translations.get(key, key)
    
    def get_all_texts(self, language: str = None) -> Dict[str, str]:
        """Возвращает все переводы для указанного языка"""
        lang = language or self.current_language
        return self.TRANSLATIONS.get(lang, self.TRANSLATIONS[settings.DEFAULT_LANGUAGE])
    
    def get_supported_languages(self) -> list:
        """Возвращает список поддерживаемых языков"""
        return settings.SUPPORTED_LANGUAGES

# Создаем глобальный экземпляр сервиса локализации
localization_service = LocalizationService() 