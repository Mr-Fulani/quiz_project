/**
 * @fileoverview Интеграция модального окна объяснения с Telegram Mini App и обработка событий опроса
 */

/**
 * Инициализирует обработчики событий для модального окна с объяснением
 * @type {Object}
 */
const PollExplanationHandler = {
  /**
   * @type {Object} - Интерфейс Telegram WebApp
   * @private
   */
  _webApp: null,

  /**
   * @type {Object} - Словарь объяснений по ID опроса
   * @private 
   */
  _explanationStorage: {},

  /**
   * Инициализирует обработчик
   * @public
   */
  init() {
    // Проверяем наличие Telegram WebApp
    if (window.Telegram && window.Telegram.WebApp) {
      this._webApp = window.Telegram.WebApp;
      console.log('Telegram WebApp обнаружен и инициализирован');
      
      // Подписываемся на события из Telegram
      this._setupEventListeners();
    } else {
      console.warn('Telegram WebApp не обнаружен. Функциональность ограничена.');
    }

    // Проверяем наличие модального окна
    if (!window.explanationModal) {
      console.error('Модальное окно объяснений не найдено! Подключите скрипт explanation-modal.js');
      return;
    }
    
    // Добавим обработчик для тестирования (временно)
    this._setupTestHandlers();
  },

  /**
   * Настраивает обработчики событий
   * @private
   */
  _setupEventListeners() {
    // Обработчик сообщений от Telegram
    if (this._webApp) {
      this._webApp.onEvent('viewportChanged', this._onViewportChanged.bind(this));
      
      // Если будет реализовано событие для опросов
      if (this._webApp.onPollAnswer) {
        this._webApp.onPollAnswer(this._onPollAnswer.bind(this));
      }
    }
    
    // Обработчик postMessage от бота
    window.addEventListener('message', this._onPostMessage.bind(this));
  },
  
  /**
   * Обработчик события изменения размеров окна
   * @private
   */
  _onViewportChanged() {
    console.log('Размер окна Telegram изменен');
    // Можно настроить адаптивность модального окна при необходимости
  },
  
  /**
   * Обработчик ответа на опрос (если будет реализован в Telegram WebApp)
   * @param {Object} pollAnswer - Данные об ответе на опрос 
   * @private
   */
  _onPollAnswer(pollAnswer) {
    console.log('Получен ответ на опрос:', pollAnswer);
    
    const { poll_id, option_index, option_text } = pollAnswer;
    
    // Проверяем, является ли выбранный вариант "Не знаю, но хочу узнать"
    if (option_text === 'Не знаю, но хочу узнать' && this._explanationStorage[poll_id]) {
      this.showExplanation(this._explanationStorage[poll_id]);
    }
  },
  
  /**
   * Обработчик сообщений от бота через postMessage
   * @param {MessageEvent} event - Событие сообщения
   * @private 
   */
  _onPostMessage(event) {
    console.log('Получено сообщение:', event.data);
    
    try {
      const data = typeof event.data === 'string' ? JSON.parse(event.data) : event.data;
      
      // Обработка команды показа объяснения
      if (data.action === 'showExplanation' && data.explanation) {
        this.showExplanation(data.explanation);
      }
      
      // Сохранение объяснения для опроса
      if (data.action === 'saveExplanation' && data.poll_id && data.explanation) {
        this.saveExplanation(data.poll_id, data.explanation);
      }
    } catch (error) {
      console.error('Ошибка при обработке сообщения:', error);
    }
  },
  
  /**
   * Настраивает тестовые обработчики для отладки
   * @private
   */
  _setupTestHandlers() {
    // Для тестирования добавим кнопку, которая будет показывать модальное окно
    document.addEventListener('DOMContentLoaded', () => {
      const testButton = document.createElement('button');
      testButton.textContent = 'Тест объяснения';
      testButton.style.position = 'fixed';
      testButton.style.bottom = '80px';
      testButton.style.right = '20px';
      testButton.style.zIndex = '100';
      testButton.style.padding = '10px';
      testButton.style.backgroundColor = '#3498db';
      testButton.style.color = 'white';
      testButton.style.border = 'none';
      testButton.style.borderRadius = '5px';
      
      testButton.addEventListener('click', () => {
        this.showExplanation('Это тестовое объяснение для проверки функциональности модального окна. Здесь будет текст из поля explanation из модели TaskTranslation.');
      });
      
      document.body.appendChild(testButton);
    });
  },
  
  /**
   * Сохраняет объяснение для опроса
   * @param {string} poll_id - ID опроса
   * @param {string} explanation - Текст объяснения
   * @public
   */
  saveExplanation(poll_id, explanation) {
    this._explanationStorage[poll_id] = explanation;
    console.log(`Объяснение для опроса ${poll_id} сохранено`);
  },
  
  /**
   * Показывает модальное окно с объяснением
   * @param {string} explanation - Текст объяснения
   * @public 
   */
  showExplanation(explanation) {
    if (window.showExplanation) {
      window.showExplanation(explanation);
    } else {
      console.error('Функция showExplanation не найдена');
    }
  }
};

// Автоматическая инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
  PollExplanationHandler.init();
});

// Экспорт для использования в других модулях
window.PollExplanationHandler = PollExplanationHandler; 