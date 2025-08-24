/**
 * JavaScript для страницы задач в mini-app
 * 
 * Этот файл содержит всю логику для обработки ответов на задачи,
 * включая выбор ответов, отправку на сервер, отображение результатов
 * и объяснений.
 * 
 * @author Mini App Team
 * @version 2.0.0
 * @updated 2025-08-24 - Fixed user initialization and telegram_id detection
 */

console.log('🚀 tasks.js загружен');
console.log('📄 tasks.js: DOM ready state:', document.readyState);
console.log('📄 tasks.js: Current URL:', window.location.href);

/**
 * Основной класс для управления задачами
 */
class TaskManager {
    /**
     * Инициализирует менеджер задач
     */
    constructor() {
        console.log('🔧 TaskManager инициализируется...');
        this.dontKnowOptions = [
            "Я не знаю, но хочу узнать",
            "I don't know, but I want to learn"
        ];
        this.init();
    }

    /**
     * Инициализирует обработчики событий
     */
    init() {
        console.log('🔧 Инициализация обработчиков...');
        this.setupAnswerHandlers();
        this.setupBackButton();
        console.log('✅ TaskManager инициализирован');
    }

    /**
     * Устанавливает обработчики для вариантов ответов
     */
    setupAnswerHandlers() {
        const answerOptions = document.querySelectorAll('.answer-option');
        console.log(`🔧 Найдено ${answerOptions.length} вариантов ответов`);
        
        answerOptions.forEach((option, index) => {
            console.log(`🔧 Настройка обработчика для ответа ${index + 1}:`, option.textContent);
            
            // Удаляем существующие обработчики
            option.removeEventListener('click', this.handleAnswerSelection.bind(this));
            
            // Добавляем класс dont-know-option, если ответ в списке
            if (this.dontKnowOptions.includes(option.dataset.answer)) {
                option.classList.add('dont-know-option');
            }
            
            // Добавляем новый обработчик
            option.addEventListener('click', this.handleAnswerSelection.bind(this));
            
            // Добавляем обработчик для отладки
            option.addEventListener('click', (e) => {
                console.log('🖱️ Клик по ответу:', option.textContent);
            });
        });
    }

    /**
     * Устанавливает обработчик для кнопки "Назад"
     */
    setupBackButton() {
        const backButton = document.querySelector('.back-button');
        if (backButton) {
            console.log('🔧 Настройка кнопки "Назад"');
            backButton.addEventListener('click', this.goBack.bind(this));
        } else {
            console.log('⚠️ Кнопка "Назад" не найдена');
        }
    }

    /**
     * Обрабатывает выбор ответа пользователем
     * @param {Event} event - Событие клика
     */
    async handleAnswerSelection(event) {
        console.log('🎯 Обработка выбора ответа');
        event.preventDefault();
        event.stopPropagation();
        
        const option = event.currentTarget;
        const taskItem = option.closest('.task-item');
        
        // Получаем данные из data-атрибутов
        const selectedAnswer = option.dataset.answer;
        const isCorrect = option.dataset.correct === 'true';
        const explanation = option.dataset.explanation;
        const taskId = taskItem.dataset.taskId;
        
        console.log('Task ID:', taskId, 'Answer:', selectedAnswer, 'Correct:', isCorrect);
        
        // Проверяем, не решена ли уже задача
        if (taskItem.dataset.solved === 'true') {
            console.log('Answer selection blocked: task already solved');
            return;
        }
        const isDontKnow = option.classList.contains('dont-know-option') || 
                          this.dontKnowOptions.includes(option.dataset.answer);
        
        console.log('Правильный ответ:', isCorrect, 'Не знаю:', isDontKnow);
        
        // Фиксируем задачу
        this.disableAllAnswers(taskItem);
        this.markSelectedAnswer(option, isCorrect);
        taskItem.dataset.solved = 'true';
        
        // Отправляем ответ на сервер
        await this.submitAnswerToServer(taskId, selectedAnswer);
        
        // Показываем правильный ответ, если выбран неправильный
        if (!isCorrect) {
            this.showCorrectAnswer(taskItem);
        }
        
        // Показываем объяснение
        this.showExplanation(taskItem);
        
        // Показываем уведомление
        this.showNotification(isCorrect, isDontKnow);
    }

    /**
     * Отправляет ответ на сервер
     * @param {number} taskId - ID задачи
     * @param {string} answer - Выбранный ответ
     */
    async submitAnswerToServer(taskId, answer) {
        try {
            // Получаем telegram_id из разных источников
            let telegramId = null;
            
            console.log('🔍 Проверяем источники telegram_id:', {
                hasCurrentUser: !!window.currentUser,
                currentUserTelegramId: window.currentUser?.telegram_id,
                hasTelegram: typeof window.Telegram !== 'undefined',
                hasWebApp: typeof window.Telegram !== 'undefined' && window.Telegram.WebApp,
                hasInitData: typeof window.Telegram !== 'undefined' && window.Telegram.WebApp ? !!window.Telegram.WebApp.initData : false,
                initDataLength: typeof window.Telegram !== 'undefined' && window.Telegram.WebApp ? window.Telegram.WebApp.initData?.length : 0,
                initDataUnsafe: typeof window.Telegram !== 'undefined' ? window.Telegram.WebApp?.initDataUnsafe : null,
                user: typeof window.Telegram !== 'undefined' ? window.Telegram.WebApp?.initDataUnsafe?.user : null,
                userId: typeof window.Telegram !== 'undefined' ? window.Telegram.WebApp?.initDataUnsafe?.user?.id : null,
                isUserInitialized: window.isUserInitialized,
                currentUserData: window.currentUser
            });
            
            // Приоритет 1: Инициализированный пользователь через /api/verify-init-data
            if (window.currentUser && window.currentUser.telegram_id) {
                telegramId = window.currentUser.telegram_id;
                console.log('✅ Получен telegram_id из window.currentUser (приоритет 1):', telegramId);
            }
            // Приоритет 2: Telegram WebApp напрямую
            else if (typeof window.Telegram !== 'undefined' && window.Telegram.WebApp && window.Telegram.WebApp.initDataUnsafe?.user?.id) {
                telegramId = window.Telegram.WebApp.initDataUnsafe.user.id;
                console.log('✅ Получен telegram_id из Telegram WebApp (приоритет 2):', telegramId);
            }
            // Приоритет 3: Ждем инициализации пользователя (если мы в Telegram)
            else if (typeof window.Telegram !== 'undefined' && window.Telegram.WebApp && window.Telegram.WebApp.initData) {
                console.log('⏳ Пользователь не инициализирован, но есть initData. Попробуем инициализировать...');
                
                // Пытаемся инициализировать пользователя вручную
                try {
                    const response = await fetch('/api/verify-init-data', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ initData: window.Telegram.WebApp.initData })
                    });
                    
                    if (response.ok) {
                        const userData = await response.json();
                        window.currentUser = userData;
                        window.isUserInitialized = true;
                        telegramId = userData.telegram_id;
                        console.log('✅ Пользователь инициализирован вручную, telegram_id:', telegramId);
                    } else {
                        console.error('❌ Ошибка инициализации пользователя:', response.status);
                    }
                } catch (error) {
                    console.error('❌ Ошибка при инициализации пользователя:', error);
                }
            }
            
            // Fallback для браузера
            if (!telegramId) {
                // Проверяем, что мы НЕ в Telegram (браузер)
                if (typeof window.Telegram === 'undefined' || !window.Telegram.WebApp) {
                    telegramId = 7827592658; // Fulani из базы данных
                    console.warn('⚠️ Браузер: используем тестовый ID существующего пользователя:', telegramId);
                } else {
                    console.error('❌ В Telegram, но не удалось получить telegram_id');
                    this.showToast('Ошибка: не удалось определить пользователя', 'error');
                    return;
                }
            }
            
            console.log('📤 Отправляем ответ на сервер:', { taskId, answer, telegramId });
            
            const response = await fetch(`/api/tasks/${taskId}/submit`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    telegram_id: telegramId,
                    answer: answer
                })
            });
            
            if (response.ok) {
                const result = await response.json();
                console.log('✅ Ответ успешно отправлен:', result);
                
                // Обновляем статистику на странице, если нужно
                if (result.total_attempts) {
                    this.updateTaskStatistics(taskId, result);
                }
            } else {
                console.error('❌ Ошибка при отправке ответа:', response.status, response.statusText);
                const errorData = await response.json().catch(() => ({}));
                console.error('Детали ошибки:', errorData);
            }
        } catch (error) {
            console.error('❌ Ошибка при отправке ответа на сервер:', error);
        }
    }

    /**
     * Обновляет статистику задачи на странице
     * @param {number} taskId - ID задачи
     * @param {Object} result - Результат от сервера
     */
    updateTaskStatistics(taskId, result) {
        // Здесь можно обновить отображение статистики на странице
        // Например, показать количество попыток, процент успешности и т.д.
        console.log('📊 Обновляем статистику для задачи', taskId, result);
    }

    /**
     * Отключает все варианты ответов
     * @param {HTMLElement} taskItem - Элемент задачи
     */
    disableAllAnswers(taskItem) {
        const answers = taskItem.querySelectorAll('.answer-option');
        answers.forEach(opt => {
            opt.style.pointerEvents = 'none';
            opt.classList.remove('active');
            opt.classList.add('disabled');
        });
    }

    /**
     * Отмечает выбранный ответ
     * @param {HTMLElement} option - Выбранный вариант ответа
     * @param {boolean} isCorrect - Правильный ли ответ
     */
    markSelectedAnswer(option, isCorrect) {
        option.classList.add('selected');
        option.classList.add(isCorrect ? 'correct' : 'incorrect');
    }

    /**
     * Показывает правильный ответ
     * @param {HTMLElement} taskItem - Элемент задачи
     */
    showCorrectAnswer(taskItem) {
        const answers = taskItem.querySelectorAll('.answer-option');
        answers.forEach(btn => {
            if (btn.dataset.correct === 'true') {
                btn.classList.add('correct');
            }
        });
    }

    /**
     * Показывает объяснение
     * @param {HTMLElement} taskItem - Элемент задачи
     */
    showExplanation(taskItem) {
        const taskId = taskItem.dataset.taskId;
        const explanationDiv = document.getElementById(`explanation-${taskId}`);
        
        if (explanationDiv) {
            explanationDiv.style.display = 'block';
            explanationDiv.scrollIntoView({ 
                behavior: 'smooth', 
                block: 'center' 
            });
        }
    }

    /**
     * Показывает уведомление о результате
     * @param {boolean} isCorrect - Правильный ли ответ
     * @param {boolean} isDontKnow - Выбрана ли опция "Не знаю"
     */
    showNotification(isCorrect, isDontKnow) {
        let message, type;
        
        if (isDontKnow) {
            message = 'Правильно! Вы выбрали "Не знаю" - это хороший подход к обучению.';
            type = 'info';
        } else if (isCorrect) {
            message = 'Правильно! Отличная работа!';
            type = 'success';
        } else {
            message = 'Неправильно. Посмотрите объяснение ниже.';
            type = 'error';
        }
        
        this.showToast(message, type);
    }

    /**
     * Показывает toast уведомление
     * @param {string} message - Текст сообщения
     * @param {string} type - Тип уведомления (success, error, info)
     */
    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        
        // Стили для toast
        toast.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 20px;
            border-radius: 8px;
            color: white;
            font-weight: 600;
            z-index: 1000;
            animation: slideIn 0.3s ease;
            max-width: 300px;
        `;
        
        // Цвета в зависимости от типа
        if (type === 'success') {
            toast.style.background = '#28a745';
        } else if (type === 'error') {
            toast.style.background = '#dc3545';
        } else {
            toast.style.background = '#007bff';
        }
        
        document.body.appendChild(toast);
        
        // Удаляем через 3 секунды
        setTimeout(() => {
            toast.remove();
        }, 3000);
    }

    /**
     * Переход назад
     */
    goBack() {
        if (typeof window.Telegram !== 'undefined' && window.Telegram.WebApp) {
            window.Telegram.WebApp.navigateTo('/');
        } else {
            window.history.back();
        }
    }
}

/**
 * Инициализация при загрузке страницы
 */
document.addEventListener('DOMContentLoaded', function() {
    console.log('📄 DOM загружен, инициализация TaskManager...');
    console.log('📄 Найдено элементов .task-item:', document.querySelectorAll('.task-item').length);
    console.log('📄 Найдено элементов .answer-option:', document.querySelectorAll('.answer-option').length);
    window.taskManager = new TaskManager();
});

// Также инициализируем, если DOM уже загружен
if (document.readyState === 'loading') {
    console.log('📄 DOM еще загружается, ждем...');
} else {
    console.log('📄 DOM уже загружен, инициализируем сразу...');
    console.log('📄 Найдено элементов .task-item:', document.querySelectorAll('.task-item').length);
    console.log('📄 Найдено элементов .answer-option:', document.querySelectorAll('.answer-option').length);
    window.taskManager = new TaskManager();
}

/**
 * Глобальная функция для совместимости с inline обработчиками
 * @param {HTMLElement} button - Кнопка ответа
 * @param {string} selectedAnswer - Выбранный ответ
 * @param {string} correctAnswer - Правильный ответ
 * @param {string} explanation - Объяснение
 */
function selectAnswer(button, selectedAnswer, correctAnswer, explanation) {
    console.log('🔧 Вызов selectAnswer');
    if (window.taskManager) {
        // Создаем событие для совместимости
        const event = {
            preventDefault: () => {},
            stopPropagation: () => {},
            currentTarget: button
        };
        window.taskManager.handleAnswerSelection(event);
    }
}

/**
 * Глобальная функция для перехода назад
 */
function goBack() {
    console.log('🔧 Вызов goBack');
    if (window.taskManager) {
        window.taskManager.goBack();
    }
} 