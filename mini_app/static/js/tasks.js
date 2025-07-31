/**
 * JavaScript для страницы задач в mini-app
 * 
 * Этот файл содержит всю логику для обработки ответов на задачи,
 * включая выбор ответов, отправку на сервер, отображение результатов
 * и объяснений.
 * 
 * @author Mini App Team
 * @version 1.0.0
 */

console.log('🚀 tasks.js загружен');

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
        
        console.log('Task ID:', taskItem.dataset.taskId, 'Answer:', option.dataset.answer);
        
        // Проверяем, не решена ли уже задача
        if (taskItem.dataset.solved === 'true') {
            console.log('Answer selection blocked: task already solved');
            return;
        }
        
        const isCorrect = option.dataset.correct === 'true';
        const isDontKnow = option.classList.contains('dont-know-option') || 
                          this.dontKnowOptions.includes(option.dataset.answer);
        
        console.log('Правильный ответ:', isCorrect, 'Не знаю:', isDontKnow);
        
        // Фиксируем задачу
        this.disableAllAnswers(taskItem);
        this.markSelectedAnswer(option, isCorrect);
        taskItem.dataset.solved = 'true';
        
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
    window.taskManager = new TaskManager();
});

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