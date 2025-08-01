/**
 * Менеджер задач для страницы подтем
 */
class TaskManager {
    constructor() {
        this.initializeHandlers();
    }

    initializeHandlers() {
        // Находим все варианты ответов
        const answerOptions = document.querySelectorAll('.answer-option');
        
        // Настраиваем обработчики для каждого варианта ответа
        answerOptions.forEach((option, index) => {
            option.addEventListener('click', (event) => {
                this.handleAnswerSelection(event);
            });
        });

        // Настраиваем кнопку "Назад"
        const backButton = document.querySelector('.back-button');
        if (backButton) {
            backButton.addEventListener('click', () => {
                this.goBack();
            });
        }
    }

    handleAnswerSelection(event) {
        const option = event.currentTarget;
        const taskItem = option.closest('.task-item');

        // Получаем данные из data-атрибутов
        const selectedAnswer = option.dataset.answer;
        const isCorrect = option.dataset.correct === 'true';
        const explanation = option.dataset.explanation;

        // Проверяем, не решена ли уже задача
        if (taskItem.classList.contains('solved')) {
            return;
        }

        // Отмечаем задачу как решенную
        taskItem.classList.add('solved');

        // Определяем результат
        const isDontKnow = selectedAnswer === 'Не знаю';

        // Показываем результат
        this.showResult(taskItem, isCorrect, isDontKnow, explanation, selectedAnswer);
    }

    showResult(taskItem, isCorrect, isDontKnow, explanation, selectedAnswer) {
        // Находим все варианты ответов в этой задаче
        const options = taskItem.querySelectorAll('.answer-option');
        
        options.forEach(option => {
            option.disabled = true;
            
            // Определяем правильный ответ
            const isThisCorrect = option.dataset.correct === 'true';
            
            if (isThisCorrect) {
                option.classList.add('correct');
            } else if (option.dataset.answer === selectedAnswer && !isCorrect) {
                option.classList.add('incorrect');
            }
        });

        // Показываем объяснение, если есть
        if (explanation) {
            const explanationDiv = taskItem.querySelector('.explanation');
            if (explanationDiv) {
                explanationDiv.textContent = explanation;
                explanationDiv.style.display = 'block';
            }
        }

        // Обновляем статистику
        this.updateStatistics(isCorrect, isDontKnow);
    }

    updateStatistics(isCorrect, isDontKnow) {
        // Здесь можно добавить логику обновления статистики
        // Например, отправка данных на сервер
    }

    goBack() {
        // Возвращаемся на предыдущую страницу
        window.history.back();
    }
}

// Инициализация при загрузке DOM
document.addEventListener('DOMContentLoaded', function() {
    window.taskManager = new TaskManager();
});

// Также инициализируем, если DOM уже загружен
if (document.readyState === 'loading') {
    // DOM еще загружается, ждем события DOMContentLoaded
} else {
    window.taskManager = new TaskManager();
}

// Глобальные функции для совместимости
window.selectAnswer = function(taskId, answer) {
    // Находим задачу и симулируем клик по ответу
    const taskItem = document.querySelector(`[data-task-id="${taskId}"]`);
    if (taskItem) {
        const answerOption = taskItem.querySelector(`[data-answer="${answer}"]`);
        if (answerOption) {
            answerOption.click();
        }
    }
};

window.goBack = function() {
    window.history.back();
}; 