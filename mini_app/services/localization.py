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
            "top_users": "Top Users",
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
            "top_users_title": "Top Users",
            "no_top_users": "No top users yet",
            "keep_playing": "Keep playing to get to the top!",
            
            # Фильтры
            "gender": "Gender",
            "age": "Age",
            "programming_language": "Programming Language",
            "rating": "Rating",
            "all": "All",
            "male": "Male",
            "female": "Female",
            "reset_filters": "Reset ",
            
            # Статистика
            "statistics_title": "Statistics",
            "total_questions": "Total Questions",
            "correct_answers": "Correct Answers",
            "incorrect_answers": "Incorrect Answers",
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
            "no_tasks_for_level": "No tasks for selected level",
            
            # Профиль - дополнительные
            "points": "Points",
            "rating": "Rating",
            "quizzes": "Quizzes",
            "success_rate": "Success Rate",
            "social_networks": "Social Networks",
            "no_social_links": "Social networks not specified.",
            "refresh_data": "Refresh Data",
            "no_statistics_data": "No data available for display.",
            
            # Профессиональная информация
            "professional_info": "Professional Information",
            "grade": "Grade",
            "technologies": "Technologies",
            "grade_junior": "Junior",
            "grade_middle": "Middle",
            "grade_senior": "Senior",
            "not_specified": "Not specified",
            "no_technologies": "No technologies specified",
            "select_grade": "Select grade",
            "select_gender": "Select gender",
            "loading_technologies": "Loading technologies...",
            
            # Персональная информация
            "years_old": "years old",
            "age_unknown": "Age not specified",
            "grade_unknown": "Grade not specified",
            "junior": "Junior",
            "middle": "Middle",
            "senior": "Senior",
            "birth_date": "Birth Date",
            "gender_unknown": "Not specified",
        },
        "ru": {
            # Навигация
            "home": "Главная",
            "profile": "Профиль",
            "top_users": "Топ юзеров",
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
            "top_users_title": "Топ юзеров",
            "no_top_users": "Пока нет лучших пользователей",
            "keep_playing": "Продолжайте играть, чтобы попасть в топ!",
            
            # Фильтры
            "gender": "Пол",
            "age": "Возраст",
            "programming_language": "Язык программирования",
            "rating": "Рейтинг",
            "all": "Все",
            "male": "Мужской",
            "female": "Женский",
            "reset_filters": "Сбросить",
            
            # Статистика
            "statistics_title": "Статистика",
            "total_questions": "Всего вопросов",
            "correct_answers": "Правильных ответов",
            "incorrect_answers": "Неправильных ответов",
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
            "no_tasks_for_level": "Нет задач выбранного уровня",
            
            # Профиль - дополнительные
            "points": "Баллов",
            "rating": "Рейтинг",
            "quizzes": "Квизов",
            "success_rate": "Успешность",
            "social_networks": "Социальные сети",
            "no_social_links": "Социальные сети не указаны.",
            "refresh_data": "Обновить данные",
            "no_statistics_data": "Пока нет данных для отображения",
            
            # Профессиональная информация
            "professional_info": "Профессиональная информация",
            "grade": "Грейд",
            "technologies": "Технологии",
            "grade_junior": "Junior",
            "grade_middle": "Middle",
            "grade_senior": "Senior",
            "not_specified": "Не указан",
            "no_technologies": "Технологии не указаны",
            "select_grade": "Выберите грейд",
            "select_gender": "Выберите пол",
            "loading_technologies": "Загрузка технологий...",
            
            # Персональная информация
            "years_old": "лет",
            "age_unknown": "Возраст не указан",
            "grade_unknown": "Грейд не указан",
            "junior": "Junior",
            "middle": "Middle",
            "senior": "Senior",
            "birth_date": "Дата рождения",
            "gender_unknown": "Не указан",
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