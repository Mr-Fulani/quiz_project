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
            "share_app": "Share App",
            "share_app_description": "Share this app with friends",
            "qr_code": "QR Code",
            "copy_link": "Copy Link",
            "link_copied": "Link copied!",
            "app_description": "Educational quiz app for learning various topics",
            "share_social": "Share on Social Media",
            "app_name": "Quiz Mini App",
            "app_features_learning": "📚 Learning",
            "app_features_quizzes": "🎯 Quizzes",
            "app_features_achievements": "🏆 Achievements",
            
            # Донаты
            "support_project": "Support Project",
            "donation_amount": "Donation Amount",
            "donation_currency": "Currency",
            "donate_button": "Donate",
            "donation_success": "Thank you for your support!",
            "donation_error": "Payment failed. Please try again.",
            "donation_processing": "Processing payment...",
            "donation_amount_placeholder": "Enter amount",
            "donation_name_placeholder": "Your name",
            "donation_email_placeholder": "Your email (optional)",
            "donation_description": "Support the development of this educational app",
            "donation_min_amount": "Minimum amount: $1",
            "donation_currency_usd": "USD ($)",
            "donation_currency_eur": "EUR (€)",
            "donation_currency_rub": "RUB (₽)",
            "donation_card_number": "Card Number",
            "donation_expiry": "MM/YY",
            "donation_cvc": "CVC",
            "donation_pay": "Pay",
            "donation_cancel": "Cancel",
            
            # Общие
            "loading": "Loading...",
            "error": "Error",
            "success": "Success",
            "confirm": "Confirm",
            "delete": "Delete",
            "edit": "Edit",
            "close": "Close",
            
            # Профиль - дополнительные
            "points": "Points",
            "rating": "Rating",
            "quizzes": "Quizzes",
            "success_rate": "Success Rate",
            "progress_topics": "Topic Progress",
            "no_progress_data": "No progress data available.",
            "social_networks": "Social Networks",
            "no_social_links": "Social networks not specified.",
            "refresh_data": "Refresh Data",
            "no_statistics_data": "No data available for display.",
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
            "share_app": "Поделиться приложением",
            "share_app_description": "Поделитесь приложением с друзьями",
            "qr_code": "QR-код",
            "copy_link": "Копировать ссылку",
            "link_copied": "Ссылка скопирована!",
            "app_description": "Образовательное приложение с квизами для изучения различных тем",
            "share_social": "Поделиться в соцсетях",
            "app_name": "Quiz Mini App",
            "app_features_learning": "📚 Обучение",
            "app_features_quizzes": "🎯 Квизы",
            "app_features_achievements": "🏆 Достижения",
            
            # Донаты
            "support_project": "Поддержать проект",
            "donation_amount": "Сумма доната",
            "donation_currency": "Валюта",
            "donate_button": "Пожертвовать",
            "donation_success": "Спасибо за вашу поддержку!",
            "donation_error": "Ошибка платежа. Попробуйте еще раз.",
            "donation_processing": "Обработка платежа...",
            "donation_amount_placeholder": "Введите сумму",
            "donation_name_placeholder": "Ваше имя",
            "donation_email_placeholder": "Ваш email (необязательно)",
            "donation_description": "Поддержите разработку этого образовательного приложения",
            "donation_min_amount": "Минимальная сумма: $1",
            "donation_currency_usd": "USD ($)",
            "donation_currency_eur": "EUR (€)",
            "donation_currency_rub": "RUB (₽)",
            "donation_card_number": "Номер карты",
            "donation_expiry": "ММ/ГГ",
            "donation_cvc": "CVC",
            "donation_pay": "Оплатить",
            "donation_cancel": "Отмена",
            
            # Общие
            "loading": "Загрузка...",
            "error": "Ошибка",
            "success": "Успешно",
            "confirm": "Подтвердить",
            "delete": "Удалить",
            "edit": "Редактировать",
            "close": "Закрыть",
            
            # Профиль - дополнительные
            "points": "Баллов",
            "rating": "Рейтинг",
            "quizzes": "Квизов",
            "success_rate": "Успешность",
            "progress_topics": "Прогресс по темам",
            "no_progress_data": "Нет данных о прогрессе.",
            "social_networks": "Социальные сети",
            "no_social_links": "Социальные сети не указаны.",
            "refresh_data": "Обновить данные",
            "no_statistics_data": "Пока нет данных для отображения",
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