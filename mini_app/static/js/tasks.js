/**
 * JavaScript для страницы задач в mini-app
 * 
 * Этот файл содержит всю логику для обработки ответов на задачи,
 * включая выбор ответов, отправку на сервер, отображение результатов
 * и объяснений.
 * 
 * @author Mini App Team
 * @version 3.0.1
 * @updated 2025-08-25 - Fixed request sending issues
 */

// Проверяем, не загружен ли уже скрипт
if (window.TaskManagerAlreadyLoaded) {
    console.log('⚠️ tasks.js уже загружен, пропускаем повторную загрузку');
    // Переинициализируем обработчики если нужно
    if (window.reinitializeBackButton) {
        console.log('🔄 Переинициализация обработчиков для уже загруженного скрипта');
        window.reinitializeBackButton();
    }
} else {
    console.log('🚀 tasks.js загружен v3.0.1');
    window.TaskManagerAlreadyLoaded = true;

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
            console.log('🔧 Версия tasks.js: 3.0.1');
            
            this.dontKnowOptions = [
                "Я не знаю, но хочу узнать",
                "I don't know, but I want to learn"
            ];
            
            // Флаг для отслеживания состояния инициализации
            this.isInitialized = false;
            this.imageOverlay = null;
            this.imageOverlayImg = null;
            this.boundEscHandler = null;
            
            this.init();
        }

        /**
         * Инициализирует обработчики событий
         */
        init() {
            console.log('🔧 Инициализация обработчиков...');
            
            // Ждем полной загрузки DOM
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', () => {
                    this.setupEventHandlers();
                });
            } else {
                this.setupEventHandlers();
            }
            
            console.log('✅ TaskManager инициализирован');
        }
        
        /**
         * Настраивает все обработчики событий
         */
        setupEventHandlers() {
            this.setupAnswerHandlers();
            this.setupBackButton();
            this.setupTaskImageHandlers();
            this.setupImageOverlay();
            this.isInitialized = true;
            console.log('✅ Обработчики событий настроены');
        }

        /**
         * Добавляет обработчики для изображений задач
         */
        setupTaskImageHandlers() {
            const taskImages = document.querySelectorAll('.task-image img');
            if (!taskImages.length) {
                console.log('ℹ️ Изображения задач не найдены, пропускаем полноэкранный режим');
                return;
            }

            taskImages.forEach((imageElement) => {
                if (imageElement.dataset.overlayBound === 'true') {
                    return;
                }

                imageElement.dataset.overlayBound = 'true';
                imageElement.addEventListener('click', () => {
                    this.openImageFullscreen(imageElement.src);
                });
            });
        }

        /**
         * Настраивает overlay для полноэкранных изображений
         */
        setupImageOverlay() {
            if (!this.imageOverlay) {
                this.imageOverlay = document.querySelector('[data-overlay="task-image-overlay"]');
            }
            if (!this.imageOverlayImg) {
                this.imageOverlayImg = document.querySelector('[data-overlay-image="task-image-overlay"]');
            }

            if (!this.imageOverlay || !this.imageOverlayImg) {
                console.warn('⚠️ Overlay для изображений не найден, пропускаем настройку');
                return;
            }

            if (!this.imageOverlay.dataset.boundClick) {
                this.imageOverlay.dataset.boundClick = 'true';
                this.imageOverlay.addEventListener('click', () => this.closeImageFullscreen());
            }

            if (!this.boundEscHandler) {
                this.boundEscHandler = (event) => this.handleOverlayKeydown(event);
                document.addEventListener('keydown', this.boundEscHandler);
            }
        }
        
        /**
         * Переинициализирует обработчики кнопки "Назад"
         */
        reinitializeBackButton() {
            console.log('🔧 Переинициализация обработчиков кнопки "Назад"...');
            this.setupBackButton();
        }

        /**
         * Открывает полноэкранный просмотр изображения
         * @param {string} src - Адрес изображения
         */
        openImageFullscreen(src) {
            if (!this.imageOverlay || !this.imageOverlayImg) {
                this.setupImageOverlay();
            }
            if (!this.imageOverlay || !this.imageOverlayImg) {
                return;
            }

            this.imageOverlayImg.src = src;
            this.imageOverlay.classList.add('is-visible');
            this.imageOverlay.setAttribute('aria-hidden', 'false');
            document.body.classList.add('task-image-overlay-open');
        }

        /**
         * Закрывает полноэкранный просмотр изображения
         */
        closeImageFullscreen() {
            if (!this.imageOverlay || !this.imageOverlayImg) {
                return;
            }

            this.imageOverlay.classList.remove('is-visible');
            this.imageOverlay.setAttribute('aria-hidden', 'true');
            document.body.classList.remove('task-image-overlay-open');

            setTimeout(() => {
                this.imageOverlayImg.src = '';
            }, 200);
        }

        /**
         * Обрабатывает нажатие Esc для закрытия overlay
         * @param {KeyboardEvent} event - Событие клавиатуры
         */
        handleOverlayKeydown(event) {
            if (event.key === 'Escape' && this.imageOverlay?.classList.contains('is-visible')) {
                this.closeImageFullscreen();
            }
        }

        /**
         * Устанавливает обработчики для вариантов ответов
         */
        setupAnswerHandlers() {
            const answerOptions = document.querySelectorAll('.answer-option');
            console.log(`🔧 Найдено ${answerOptions.length} вариантов ответов`);
            
            answerOptions.forEach((option, index) => {
                console.log(`🔧 Настройка обработчика для ответа ${index + 1}:`, option.textContent.trim());
                
                // Проверяем наличие необходимых data-атрибутов
                const requiredAttrs = ['answer', 'correct', 'explanation'];
                const missingAttrs = requiredAttrs.filter(attr => !option.hasAttribute(`data-${attr}`));
                
                if (missingAttrs.length > 0) {
                    console.error(`❌ У элемента отсутствуют атрибуты: data-${missingAttrs.join(', data-')}`, option);
                    return;
                }
                
                // Проверяем, что у родительского элемента есть task-id
                const taskItem = option.closest('.task-item');
                if (!taskItem || !taskItem.dataset.taskId) {
                    console.error('❌ Не найден родительский элемент .task-item или отсутствует data-task-id', option);
                    return;
                }
                
                // Удаляем существующие обработчики
                const newOption = option.cloneNode(true);
                option.parentNode.replaceChild(newOption, option);
                
                // Добавляем класс dont-know-option, если ответ в списке
                if (this.dontKnowOptions.includes(newOption.dataset.answer)) {
                    newOption.classList.add('dont-know-option');
                }
                
                // Добавляем новый обработчик
                newOption.addEventListener('click', (e) => this.handleAnswerSelection(e));
                
                console.log(`✅ Обработчик установлен для ответа: "${newOption.textContent.trim()}"`);
            });
            
            // Добавляем логику для уже решенных задач после установки всех обработчиков
            // Перебираем все задачи для начальной настройки
            document.querySelectorAll('.task-item').forEach(taskItem => {
                const taskId = taskItem.dataset.taskId;
                
                // Всегда показываем объяснение автоматически (без прокрутки при инициализации)
                this.showExplanation(taskItem, true);

                if (taskItem.dataset.solved === 'true') {
                    // Блокируем все ответы, кроме "Не знаю"
                    this.disableAllAnswers(taskItem, true);
                    
                    // Отмечаем правильный ответ, если задача уже решена
                    const answerOptions = taskItem.querySelectorAll('.answer-option');
                    answerOptions.forEach(option => {
                        if (option.dataset.correct === 'true') {
                            option.classList.add('correct');
                        }
                    });
                    console.log(`✅ Задача ${taskId} уже решена. Ответы заблокированы (кроме "Не знаю") и объяснение показано.`);
                }
            });

            // Если сервер не проставил data-solved, проверим через API и заблокируем
            this.ensureSolvedStateFromServer();
        }

        async ensureSolvedStateFromServer() {
            try {
                const root = document.getElementById('tasks-root');
                if (!root) return;
                const subtopicId = root.dataset.subtopicId;
                const language = root.dataset.language || 'en';
                const telegramId = await this.getTelegramId();
                if (!subtopicId || !telegramId) return;

                const url = `/api/topic/${encodeURIComponent(subtopicId)}?lang=${encodeURIComponent(language)}&telegram_id=${encodeURIComponent(telegramId)}`;
                // В нашем роутинге /topic/{topic_id} отдаёт HTML, поэтому используем прямой Django endpoint
                const response = await fetch(`/api/subtopics/${encodeURIComponent(subtopicId)}/?language=${encodeURIComponent(language)}&telegram_id=${encodeURIComponent(telegramId)}`);
                if (!response.ok) return;
                const data = await response.json();
                const results = data.results || [];
                const solvedIds = new Set(results.filter(t => t.is_solved).map(t => String(t.id)));

                document.querySelectorAll('.task-item').forEach(taskItem => {
                    const taskId = taskItem.dataset.taskId;
                    if (solvedIds.has(String(taskId))) {
                        taskItem.dataset.solved = 'true';
                        // Блокируем все ответы, кроме "Не знаю"
                        this.disableAllAnswers(taskItem, true);
                        this.showCorrectAnswer(taskItem);
                        this.showExplanation(taskItem, true);
                    }
                });
            } catch (e) {
                console.warn('ensureSolvedStateFromServer failed:', e);
            }
        }

        /**
         * Устанавливает обработчик для кнопки "Назад"
         */
        setupBackButton() {
            const backButton = document.querySelector('.back-button');
            if (backButton) {
                console.log('🔧 Настройка кнопки "Назад"');
                backButton.addEventListener('click', () => this.goBack());
            } else {
                console.log('⚠️ Кнопка "Назад" не найдена');
            }
        }

        /**
         * Получает telegram_id пользователя
         * @returns {Promise<string|null>} telegram_id или null
         */
        async getTelegramId() {
            console.log('🔍 Получение telegram_id...');
            
            // Проверяем текущего пользователя
            if (window.currentUser && window.currentUser.telegram_id) {
                console.log('✅ telegram_id из window.currentUser:', window.currentUser.telegram_id);
                return window.currentUser.telegram_id;
            }
            
            // Проверяем Telegram WebApp initDataUnsafe
            if (typeof window.Telegram !== 'undefined' && 
                window.Telegram.WebApp && 
                window.Telegram.WebApp.initDataUnsafe && 
                window.Telegram.WebApp.initDataUnsafe.user && 
                window.Telegram.WebApp.initDataUnsafe.user.id) {
                
                const telegramId = window.Telegram.WebApp.initDataUnsafe.user.id;
                console.log('✅ telegram_id из Telegram WebApp:', telegramId);
                return telegramId.toString();
            }
            
            // Добавляем подробное логирование для отладки
            console.log('🔍 Подробная проверка Telegram WebApp:');
            console.log('  - window.Telegram exists:', typeof window.Telegram !== 'undefined');
            if (typeof window.Telegram !== 'undefined') {
                console.log('  - window.Telegram.WebApp exists:', !!window.Telegram.WebApp);
                if (window.Telegram.WebApp) {
                    console.log('  - initDataUnsafe exists:', !!window.Telegram.WebApp.initDataUnsafe);
                    console.log('  - initDataUnsafe.user exists:', !!window.Telegram.WebApp.initDataUnsafe?.user);
                    console.log('  - initDataUnsafe.user.id exists:', !!window.Telegram.WebApp.initDataUnsafe?.user?.id);
                    console.log('  - initDataUnsafe.user.id value:', window.Telegram.WebApp.initDataUnsafe?.user?.id);
                    console.log('  - initData exists:', !!window.Telegram.WebApp.initData);
                    console.log('  - initData length:', window.Telegram.WebApp.initData?.length);
                    console.log('  - initData value (first 100 chars):', window.Telegram.WebApp.initData?.substring(0, 100));
                }
            }
            
            // Пытаемся получить через API
            if (typeof window.Telegram !== 'undefined' && 
                window.Telegram.WebApp && 
                window.Telegram.WebApp.initData) {
                
                console.log('🔧 Запрос telegram_id через API...');
                try {
                    const response = await fetch('/api/verify-init-data', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ initData: window.Telegram.WebApp.initData })
                    });
                    
                    if (response.ok) {
                        const userData = await response.json();
                        if (userData.telegram_id) {
                            window.currentUser = userData;
                            window.isUserInitialized = true;
                            console.log('✅ telegram_id получен через API:', userData.telegram_id);
                            return userData.telegram_id.toString();
                        }
                    } else {
                        console.error('❌ Ошибка при получении telegram_id:', response.status);
                    }
                } catch (error) {
                    console.error('❌ Ошибка запроса telegram_id:', error);
                }
            }
            
            // Fallback для тестирования в браузере (режим разработки)
            // Проверяем различные способы определения тестового режима
            const isDevMode = 
                window.location.hostname === 'localhost' || 
                window.location.hostname === '127.0.0.1' ||
                window.location.hostname.includes('ngrok') ||
                window.location.hostname.includes('ngrok-free.dev') ||
                window.location.search.includes('test_mode=true') ||
                localStorage.getItem('test_mode') === 'true';
            
            if (isDevMode) {
                // Сначала проверяем URL параметр
                const urlParams = new URLSearchParams(window.location.search);
                const testIdFromUrl = urlParams.get('test_telegram_id');
                
                // Затем проверяем localStorage
                const testIdFromStorage = localStorage.getItem('test_telegram_id');
                
                // Используем ID из URL, localStorage или дефолтный
                const testTelegramId = testIdFromUrl || testIdFromStorage || 975113235; // Mr_Fulani из БД
                
                console.log('🔧 ТЕСТОВЫЙ РЕЖИМ: Используем fallback telegram_id для браузера');
                console.log('   Hostname:', window.location.hostname);
                console.log('   Test ID из URL:', testIdFromUrl || 'не указан');
                console.log('   Test ID из localStorage:', testIdFromStorage || 'не указан');
                console.log('✅ Установлен тестовый telegram_id:', testTelegramId);
                
                // Сохраняем в window.currentUser для последующего использования
                if (!window.currentUser) {
                    window.currentUser = { telegram_id: parseInt(testTelegramId) };
                } else {
                    window.currentUser.telegram_id = parseInt(testTelegramId);
                }
                
                return testTelegramId.toString();
            } else {
                console.error('❌ Не удалось получить telegram_id в продакшене');
                console.error('❌ Проверьте, что мини-апп запущен из Telegram');
                return null;
            }
        }

        /**
         * Обрабатывает выбор ответа пользователем
         * @param {Event} event - Событие клика
         */
        async handleAnswerSelection(event) {
            console.log('🎯 === НАЧАЛО ОБРАБОТКИ ВЫБОРА ОТВЕТА ===');
            event.preventDefault();
            event.stopPropagation();
            
            const option = event.currentTarget;
            const taskItem = option.closest('.task-item');
            
            // Валидация элементов
            if (!taskItem) {
                console.error('❌ Не найден родительский элемент .task-item');
                return;
            }
            
            // Получаем данные из data-атрибутов
            const selectedAnswer = option.dataset.answer;
            const isCorrect = option.dataset.correct === 'true';
            const explanation = option.dataset.explanation;
            const taskId = taskItem.dataset.taskId;
            
            console.log('📋 Данные задачи:', {
                taskId,
                selectedAnswer,
                isCorrect,
                hasExplanation: !!explanation
            });
            
            // Валидация данных
            if (!taskId) {
                console.error('❌ Отсутствует taskId');
                return;
            }
            
            if (!selectedAnswer) {
                console.error('❌ Отсутствует selectedAnswer');
                return;
            }
            
            const isDontKnow = option.classList.contains('dont-know-option') || 
                              this.dontKnowOptions.includes(selectedAnswer);
            
            // Если задача уже решена и это клик на "Не знаю" - просто переключаем объяснение без отправки на сервер
            if (taskItem.dataset.solved === 'true' && isDontKnow) {
                console.log('📖 Задача уже решена, переключаем объяснение без отправки на сервер');
                this.toggleExplanation(taskItem);
                return;
            }
            
            // Проверяем, не решена ли уже задача (для обычных ответов)
            if (taskItem.dataset.solved === 'true' && !isDontKnow) {
                console.log('⚠️ Задача уже решена, игнорируем клик');
                return;
            }
            
            console.log('🔍 Статус ответа:', { isCorrect, isDontKnow });
            
            // Блокируем интерфейс (кроме кнопки "Не знаю", которая всегда остается активной)
            this.disableAllAnswers(taskItem, true);
            this.markSelectedAnswer(option, isCorrect);
            
            // Если это НЕ "Не знаю", помечаем задачу как решенную (но объяснение не показываем)
            if (!isDontKnow) {
                taskItem.dataset.solved = 'true';
            }
            
            // Показываем индикатор загрузки
            this.showLoadingToast(window.t ? window.t('submitting_answer', 'Отправляем ответ...') : 'Отправляем ответ...');
            
            try {
                // Отправляем ответ на сервер
                console.log('📤 Начинаем отправку ответа на сервер...');
                const submitResult = await this.submitAnswerToServer(taskId, selectedAnswer);
                
                if (submitResult && submitResult.success) {
                    console.log('✅ Ответ успешно отправлен');
                    
                    // Показываем правильный ответ, если выбран неправильный
                    if (!isCorrect && !isDontKnow) {
                        this.showCorrectAnswer(taskItem);
                    }
                    
                    // Переключаем объяснение для варианта "Не знаю, но хочу узнать"
                    if (isDontKnow) {
                        this.toggleExplanation(taskItem);
                        taskItem.dataset.solved = 'true';
                    }
                    
                    // Показываем уведомление
                    this.showNotification(isCorrect, isDontKnow);
                } else if (submitResult && submitResult.status === 409) {
                    console.log('ℹ️ Ответ уже был отправлен ранее. Блокируем повторные клики.');
                    taskItem.dataset.solved = 'true';
                    // Блокируем все ответы, кроме "Не знаю"
                    this.disableAllAnswers(taskItem, true);
                    // Подсветим правильный ответ
                    this.showCorrectAnswer(taskItem);
                    // Для "Не знаю" переключаем объяснение, но не показываем сообщение об ошибке
                    if (isDontKnow) {
                        this.toggleExplanation(taskItem);
                    } else {
                        this.showToast(window.t ? window.t('already_answered', 'Вы уже отвечали на этот вопрос') : 'Вы уже отвечали на этот вопрос', 'info');
                    }
                } else {
                    console.error('❌ Не удалось отправить ответ');
                    // Откатываем изменения интерфейса
                    this.enableAllAnswers(taskItem);
                    taskItem.dataset.solved = 'false';
                    option.classList.remove('selected', 'correct', 'incorrect');
                }
            } catch (error) {
                console.error('❌ Критическая ошибка при обработке ответа:', error);
                this.showToast(window.t ? window.t('error_occurred', 'Произошла ошибка. Попробуйте еще раз.') : 'Произошла ошибка. Попробуйте еще раз.', 'error');
                
                // Откатываем изменения
                this.enableAllAnswers(taskItem);
                taskItem.dataset.solved = 'false';
                option.classList.remove('selected', 'correct', 'incorrect');
            }
            
            console.log('🏁 === КОНЕЦ ОБРАБОТКИ ВЫБОРА ОТВЕТА ===');
        }

        /**
         * Отправляет ответ на сервер
         * @param {string} taskId - ID задачи
         * @param {string} answer - Выбранный ответ
         * @returns {Promise<boolean>} Успешно ли отправлен ответ
         */
        async submitAnswerToServer(taskId, answer) {
            console.log('🚀 === НАЧАЛО ОТПРАВКИ НА СЕРВЕР ===');
            console.log('📤 Параметры:', { taskId, answer });
            
            try {
                // Получаем telegram_id
                const telegramId = await this.getTelegramId();
                
                if (!telegramId) {
                    console.error('❌ Не удалось получить telegram_id');
                    this.showToast(window.t ? window.t('error_determine_user', 'Ошибка: не удалось определить пользователя. Пожалуйста, авторизуйтесь, чтобы участвовать в опросах и отслеживать свою статистику.') : 'Ошибка: не удалось определить пользователя. Пожалуйста, авторизуйтесь, чтобы участвовать в опросах и отслеживать свою статистику.', 'error');
                    return { success: false, error: 'telegram_id_not_found' };
                }
                
                console.log('✅ Используем telegram_id:', telegramId);
                
                // Подготавливаем заголовки
                const headers = {
                    'Content-Type': 'application/json',
                };
                
                // Подготавливаем данные для отправки
                const requestData = {
                    telegram_id: parseInt(telegramId),
                    answer: answer
                };
                
                // Добавляем initData если доступен
                if (typeof window.Telegram !== 'undefined' && 
                    window.Telegram.WebApp && 
                    window.Telegram.WebApp.initData) {
                    
                    headers['X-Telegram-Init-Data'] = window.Telegram.WebApp.initData;
                    requestData.initData = window.Telegram.WebApp.initData;
                    console.log('🔧 Добавлены данные Telegram');
                }
                
                const url = `/api/tasks/${taskId}/submit-mini-app/`;
                console.log('🌐 URL запроса:', url);
                console.log('📋 Данные запроса:', {
                    ...requestData,
                    initData: requestData.initData ? '[СКРЫТО]' : undefined
                });
                console.log('📋 Заголовки:', {
                    ...headers,
                    'X-Telegram-Init-Data': headers['X-Telegram-Init-Data'] ? '[СКРЫТО]' : undefined
                });
                
                // Отправляем запрос
                console.log('📡 Отправляем запрос...');
                const response = await fetch(url, {
                    method: 'POST',
                    headers: headers,
                    body: JSON.stringify(requestData)
                });
                
                console.log('📥 Получен ответ:', {
                    status: response.status,
                    statusText: response.statusText,
                    ok: response.ok,
                    headers: Object.fromEntries(response.headers.entries())
                });
                
                if (response.ok) {
                    const result = await response.json();
                    console.log('✅ Успешный ответ от сервера:', result);
                    
                    // Обновляем статистику если есть
                    if (result.total_attempts) {
                        this.updateTaskStatistics(taskId, result);
                    }
                    
                    return { success: true, status: response.status, result };
                } else {
                    console.error('❌ Ошибка HTTP:', response.status, response.statusText);
                    
                    let errorMessage = `Ошибка сервера: ${response.status}`;
                    try {
                        const errorData = await response.json();
                        console.error('📄 Детали ошибки:', errorData);
                        if (errorData.error) {
                            errorMessage = errorData.error;
                        }
                    } catch (e) {
                        console.error('❌ Не удалось прочитать тело ошибки:', e);
                    }
                    
                    // Для 409 (повторная отправка) показываем информационное сообщение
                    if (response.status === 409) {
                        this.showToast(window.t ? window.t('already_answered', 'Вы уже отвечали на этот вопрос') : 'Вы уже отвечали на этот вопрос', 'info');
                    } else {
                        this.showToast(errorMessage, 'error');
                    }
                    return { success: false, status: response.status, error: errorMessage };
                }
            } catch (error) {
                console.error('❌ Критическая ошибка при отправке:', error);
                this.showToast(window.t ? window.t('network_error', 'Ошибка сети. Проверьте подключение.') : 'Ошибка сети. Проверьте подключение.', 'error');
                return { success: false, status: 0, error: 'network' };
            } finally {
                console.log('🏁 === КОНЕЦ ОТПРАВКИ НА СЕРВЕР ===');
            }
        }

        /**
         * Обновляет статистику задачи на странице
         * @param {string} taskId - ID задачи
         * @param {Object} result - Результат от сервера
         */
        updateTaskStatistics(taskId, result) {
            console.log('📊 Обновляем статистику для задачи', taskId, result);
            // Здесь можно добавить код для обновления UI со статистикой
        }

        /**
         * Отключает все варианты ответов (кроме кнопки "Не знаю", если keepDontKnowActive = true)
         * @param {HTMLElement} taskItem - Элемент задачи
         * @param {boolean} keepDontKnowActive - Если true, кнопка "Не знаю" остается активной
         */
        disableAllAnswers(taskItem, keepDontKnowActive = false) {
            const answers = taskItem.querySelectorAll('.answer-option');
            answers.forEach(opt => {
                const isDontKnow = opt.classList.contains('dont-know-option') || 
                                this.dontKnowOptions.includes(opt.dataset.answer);
                
                // Если это кнопка "Не знаю" и нужно оставить её активной, пропускаем
                if (keepDontKnowActive && isDontKnow) {
                    return;
                }
                
                opt.style.pointerEvents = 'none';
                opt.classList.remove('active');
                opt.classList.add('disabled');
            });
        }

        /**
         * Включает все варианты ответов (для отката)
         * @param {HTMLElement} taskItem - Элемент задачи
         */
        enableAllAnswers(taskItem) {
            const answers = taskItem.querySelectorAll('.answer-option');
            answers.forEach(opt => {
                opt.style.pointerEvents = '';
                opt.classList.remove('disabled');
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
         * Форматирует ссылки (Markdown и сырые), экранируя остальной текст, если требуется.
         * @param {string} text - Текст или уже экранированный HTML.
         * @param {boolean} isEscaped - Если true, текст уже прошел escapeHtml.
         */
        formatInlineLinks(text, isEscaped = false) {
            if (!text) return '';
            
            const escapeHtml = (str) => {
                const div = document.createElement('div');
                div.textContent = str;
                return div.innerHTML;
            };
            
            let processed = isEscaped ? text : escapeHtml(text);
            
            // Заменяем Markdown-ссылки [Текст](https://...)
            processed = processed.replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, (match, title, url) => {
                const unescapedUrl = url.replace(/&amp;/g, '&');
                return `<a href="${unescapedUrl}" class="source-link" target="_blank" rel="noopener noreferrer">${title}</a>`;
            });
            
            // Выделяем сырые ссылки, перед которыми нет кавычек (не находятся внутри готовых HTML-тегов)
            // Исключаем ссылки, которые уже являются частью <a> тега (простая проверка на префикс)
            processed = processed.replace(/(^|[^="'])(https?:\/\/[^\s<)\]"']+)/g, (match, prefix, url) => {
                const unescapedUrl = url.replace(/&amp;/g, '&');
                // Если ссылка кончается на точку или запятую, исключаем её из url
                let cleanUrl = url;
                let suffix = '';
                if (url.match(/[.,;!?]$/)) {
                    suffix = url.slice(-1);
                    cleanUrl = url.slice(0, -1);
                }
                return `${prefix}<a href="${unescapedUrl}" class="source-link" target="_blank" rel="noopener noreferrer">${cleanUrl}</a>${suffix}`;
            });
            
            return processed;
        }

        /**
         * Форматирует текст объяснения: выделяет заголовки, списки и код.
         * @param {string} text - Исходный текст.
         * @returns {string} - Отформатированный HTML.
         */
        formatExplanation(text) {
            if (!text) return '';
            
            let formatted = text;
            
            // Функция для экранирования HTML
            const escapeHtml = (text) => {
                const div = document.createElement('div');
                div.textContent = text;
                return div.innerHTML;
            };
            
            // Сначала выделяем код в обратных кавычках (чтобы не трогать его дальше)
            const codeBlocks = [];
            formatted = formatted.replace(/`([^`]+)`/g, (match, code) => {
                const placeholder = `__CODE_${codeBlocks.length}__`;
                codeBlocks.push(`<code>${escapeHtml(code)}</code>`);
                return placeholder;
            });
            
            // Выделяем блоки кода (```код```)
            formatted = formatted.replace(/```([\s\S]*?)```/g, (match, code) => {
                const placeholder = `__CODEBLOCK_${codeBlocks.length}__`;
                codeBlocks.push(`<pre><code>${escapeHtml(code.trim())}</code></pre>`);
                return placeholder;
            });
            
            // Убираем заголовок "Step-by-step explanation:" или аналогичные (если есть)
            formatted = formatted.replace(/^(Step-by-step explanation:|Пошаговое объяснение:|Adım adım açıklama:|شرح خطوة بخطوة:)\s*\n?/im, '');
            
            // Преобразуем нумерованный список (1. текст)
            const lines = formatted.split('\n');
            let inList = false;
            let listItems = [];
            let result = [];
            
            lines.forEach((line, index) => {
                const trimmed = line.trim();
                
                // Пропускаем пустые строки, но не закрываем список, если следующий элемент тоже список
                if (!trimmed) {
                    // Проверяем следующий элемент
                    const nextLine = index < lines.length - 1 ? lines[index + 1].trim() : '';
                    const nextIsListItem = nextLine.match(/^(\d+)\.\s+(.+)$/);
                    
                    // Закрываем список только если следующий элемент НЕ является элементом списка
                    if (inList && listItems.length > 0 && !nextIsListItem) {
                        result.push('<ol>' + listItems.join('') + '</ol>');
                        listItems = [];
                        inList = false;
                    }
                    return;
                }
                
                // Проверяем, является ли строка блоком кода
                if (trimmed.startsWith('__CODEBLOCK_') && trimmed.endsWith('__')) {
                    // Закрываем список перед блоком кода, если он открыт
                    if (inList && listItems.length > 0) {
                        result.push('<ol>' + listItems.join('') + '</ol>');
                        listItems = [];
                        inList = false;
                    }
                    const idx = parseInt(trimmed.match(/__CODEBLOCK_(\d+)__/)[1]);
                    result.push(codeBlocks[idx] || '');
                    return;
                }
                
                // Проверяем, является ли строка элементом списка
                const listMatch = trimmed.match(/^(\d+)\.\s+(.+)$/);
                if (listMatch) {
                    if (!inList) inList = true;
                    let itemText = listMatch[2];
                    // Восстанавливаем код в элементах списка
                    itemText = itemText.replace(/__CODE_(\d+)__/g, (_, idx) => codeBlocks[parseInt(idx)] || '');
                    listItems.push(`<li>${itemText}</li>`);
                } else {
                    // Закрываем список перед обычным текстом
                    if (inList && listItems.length > 0) {
                        result.push('<ol>' + listItems.join('') + '</ol>');
                        listItems = [];
                        inList = false;
                    }
                    // Восстанавливаем код в обычных строках
                    let processedLine = trimmed.replace(/__CODE_(\d+)__/g, (_, idx) => codeBlocks[parseInt(idx)] || '');
                    // Восстанавливаем блоки кода
                    processedLine = processedLine.replace(/__CODEBLOCK_(\d+)__/g, (_, idx) => codeBlocks[parseInt(idx)] || '');
                    
                    // Форматируем ссылки в строке
                    processedLine = this.formatInlineLinks(processedLine, true);
                    
                    result.push(`<p>${processedLine}</p>`);
                }
            });
            
            // Закрываем список, если он остался открытым
            if (inList && listItems.length > 0) {
                result.push('<ol>' + listItems.join('') + '</ol>');
            }
            
            return result.join('');
        }

        /**
         * Показывает объяснение
         * @param {HTMLElement} taskItem - Элемент задачи
         */
        /**
         * Переключает видимость объяснения (показывает/скрывает)
         * @param {HTMLElement} taskItem - Элемент задачи
         */
        toggleExplanation(taskItem) {
            const taskId = taskItem.dataset.taskId;
            const explanationDiv = document.getElementById(`explanation-${taskId}`);
            
            if (explanationDiv) {
                // Проверяем видимость через computed style
                const computedStyle = window.getComputedStyle(explanationDiv);
                const isVisible = computedStyle.display !== 'none' && 
                                 explanationDiv.style.display !== 'none';
                
                if (isVisible) {
                    // Скрываем объяснение
                    explanationDiv.style.display = 'none';
                    console.log('📖 Объяснение скрыто для задачи', taskId);
                } else {
                    // Показываем объяснение
                    this.showExplanation(taskItem);
                    console.log('📖 Объяснение показано для задачи', taskId);
                }
            }
        }

        /**
         * Показывает объяснение задачи
         * @param {HTMLElement} taskItem - Элемент задачи
         * @param {boolean} skipScroll - Если true, не прокручивать к объяснению
         */
        showExplanation(taskItem, skipScroll = false) {
            const taskId = taskItem.dataset.taskId;
            const explanationDiv = document.getElementById(`explanation-${taskId}`);
            
            if (explanationDiv) {
                // Получаем исходный текст объяснения
                const explanationContent = explanationDiv.querySelector('.explanation-content');
                if (explanationContent) {
                    const explanationText = explanationContent.querySelector('.explanation-text');
                    if (explanationText) {
                        // Проверяем, не отформатирован ли уже текст
                        if (!explanationText.dataset.formatted) {
                            // Получаем исходный текст - используем innerHTML если есть, иначе textContent
                            let originalText = explanationText.innerHTML;
                            // Если innerHTML пустой или содержит только теги, используем textContent
                            if (!originalText || originalText.trim() === '' || originalText.trim().startsWith('<')) {
                                originalText = explanationText.textContent || explanationText.innerText;
                            } else {
                                // Если innerHTML содержит текст, но он может быть в тегах, извлекаем текст
                                const tempDiv = document.createElement('div');
                                tempDiv.innerHTML = originalText;
                                originalText = tempDiv.textContent || tempDiv.innerText || originalText;
                            }
                            
                            if (originalText) {
                                console.log('📝 Исходный текст объяснения:', originalText.substring(0, 200));
                                // Форматируем текст
                                let formatted = this.formatExplanation(originalText);
                                
                                // Добавляем источник, если он есть
                                const sourceName = taskItem.dataset.sourceName || '';
                                const sourceLink = taskItem.dataset.sourceLink || '';
                                
                                if (sourceName || sourceLink) {
                                    let sourceHtml = '';
                                    if (sourceLink) {
                                        // Экранируем название источника, если оно есть
                                        const displayName = sourceName ? sourceName : sourceLink;
                                        sourceHtml = `<a href="${sourceLink}" class="source-link" target="_blank" rel="noopener noreferrer">${displayName}</a>`;
                                    } else {
                                        // Если указано только имя, форматируем возможные ссылки в нем
                                        sourceHtml = `<span class="source-text">${this.formatInlineLinks(sourceName, false)}</span>`;
                                    }
                                    formatted += `<div class="explanation-source">${sourceHtml}</div>`;
                                }
                                
                                console.log('📝 Отформатированный HTML:', formatted.substring(0, 500));
                                // Заменяем содержимое на отформатированное
                                explanationText.innerHTML = formatted;
                                explanationText.dataset.formatted = 'true';
                            }
                        }
                    }
                }
                
                explanationDiv.style.display = 'block';
                if (!skipScroll) {
                    setTimeout(() => {
                        explanationDiv.scrollIntoView({ 
                            behavior: 'smooth', 
                            block: 'center' 
                        });
                    }, 100);
                }
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
                message = window.t ? window.t('dont_know_message', 'Правильно! Вы выбрали "Не знаю" - это хороший подход к обучению.') : 'Правильно! Вы выбрали "Не знаю" - это хороший подход к обучению.';
                type = 'info';
            } else if (isCorrect) {
                message = window.t ? window.t('correct_answer_message', 'Правильно! Отличная работа!') : 'Правильно! Отличная работа!';
                type = 'success';
            } else {
                message = window.t ? window.t('incorrect_answer_message', 'Неправильно. Посмотрите объяснение ниже.') : 'Неправильно. Посмотрите объяснение ниже.';
                type = 'error';
            }
            
            this.showToast(message, type);
        }

        /**
         * Показывает toast с индикатором загрузки
         * @param {string} message - Текст сообщения
         */
        showLoadingToast(message) {
            this.hideAllToasts();
            
            const toast = document.createElement('div');
            toast.className = 'toast toast-loading';
            toast.innerHTML = `
                <div style="display: flex; align-items: center; gap: 10px;">
                    <div class="spinner" style="
                        width: 20px;
                        height: 20px;
                        border: 2px solid rgba(255,255,255,0.3);
                        border-top: 2px solid white;
                        border-radius: 50%;
                        animation: spin 1s linear infinite;
                    "></div>
                    <span>${message}</span>
                </div>
            `;
            
            this.styleToast(toast, '#007bff');
            document.body.appendChild(toast);
            
            // Добавляем анимацию spinner
            const style = document.createElement('style');
            style.textContent = `
                @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }
            `;
            document.head.appendChild(style);
            
            toast.dataset.loading = 'true';
        }

        /**
         * Показывает toast уведомление
         * @param {string} message - Текст сообщения
         * @param {string} type - Тип уведомления (success, error, info)
         */
        showToast(message, type = 'info') {
            this.hideAllToasts();
            
            const toast = document.createElement('div');
            toast.className = `toast toast-${type}`;
            toast.textContent = message;
            
            // Цвет в зависимости от типа
            let backgroundColor;
            if (type === 'success') {
                backgroundColor = '#28a745';
            } else if (type === 'error') {
                backgroundColor = '#dc3545';
            } else {
                backgroundColor = '#007bff';
            }
            
            this.styleToast(toast, backgroundColor);
            document.body.appendChild(toast);
            
            // Автоматически скрываем через 4 секунды
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.remove();
                }
            }, 4000);
        }
        
        /**
         * Применяет стили к toast элементу
         * @param {HTMLElement} toast - Toast элемент
         * @param {string} backgroundColor - Цвет фона
         */
        styleToast(toast, backgroundColor) {
            toast.style.cssText = `
                position: fixed;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                padding: 15px 20px;
                border-radius: 8px;
                color: white;
                font-weight: 600;
                z-index: 1000;
                max-width: min(350px, calc(100vw - 40px));
                width: 90%;
                text-align: center;
                box-shadow: 0 4px 12px rgba(0,0,0,0.3);
                background: ${backgroundColor};
                animation: fadeInScale 0.3s ease;
            `;
            
            // Добавляем CSS анимацию если её нет
            if (!document.querySelector('#toast-animations')) {
                const style = document.createElement('style');
                style.id = 'toast-animations';
                style.textContent = `
                    @keyframes fadeInScale {
                        from {
                            transform: translate(-50%, -50%) scale(0.9);
                            opacity: 0;
                        }
                        to {
                            transform: translate(-50%, -50%) scale(1);
                            opacity: 1;
                        }
                    }
                `;
                document.head.appendChild(style);
            }
        }
        
        /**
         * Скрывает все существующие toast'ы
         */
        hideAllToasts() {
            const existingToasts = document.querySelectorAll('.toast');
            existingToasts.forEach(toast => {
                if (toast.parentNode) {
                toast.remove();
                }
            });
        }

        /**
         * Переход назад
         */
        goBack() {
            console.log('🔙 Переход назад...');
            
            // Получаем текущий URL для определения логики возврата
            const currentUrl = window.location.pathname;
            console.log('🔍 Текущий URL:', currentUrl);
            
            // Если мы на странице задач подтемы, возвращаемся на страницу подтем
            if (currentUrl.includes('/subtopic/') && currentUrl.includes('/tasks')) {
                this.goBackToSubtopic();
                return;
            }
            
            // Для других случаев используем стандартную логику
            if (typeof window.Telegram !== 'undefined' && 
                window.Telegram.WebApp && 
                typeof window.Telegram.WebApp.close === 'function') {
                window.Telegram.WebApp.close();
            } else {
                window.history.back();
            }
        }
        
        /**
         * Возврат на страницу подтем
         */
        goBackToSubtopic() {
            console.log('🔙 Возврат на страницу подтем...');
            
            // Получаем ID темы из data-атрибута контейнера
            const tasksRoot = document.getElementById('tasks-root');
            if (!tasksRoot) {
                console.error('❌ Контейнер tasks-root не найден');
                window.history.back();
                return;
            }
            
            const topicId = tasksRoot.dataset.topicId;
            if (!topicId) {
                console.error('❌ ID темы не найден в data-атрибутах');
                // Fallback: используем ID подтемы
                const subtopicId = tasksRoot.dataset.subtopicId;
                if (subtopicId) {
                    console.log('🔍 Используем fallback: ID подтемы для возврата:', subtopicId);
                    const currentLang = window.currentLanguage || 'en';
                    const backUrl = `/topic/${subtopicId}?lang=${currentLang}`;
                    this.navigateToSubtopic(backUrl);
                    return;
                }
                window.history.back();
                return;
            }
            
            console.log('🔍 ID темы для возврата:', topicId);
            
            // Формируем URL для возврата на страницу подтем
            const currentLang = window.currentLanguage || 'en';
            const backUrl = `/topic/${topicId}?lang=${currentLang}`;
            
            console.log('🔙 Переходим на:', backUrl);
            
            // Используем AJAX навигацию для возврата
            this.navigateToSubtopic(backUrl);
        }
        
        /**
         * AJAX навигация на страницу подтем
         */
        async navigateToSubtopic(url) {
            try {
                console.log('📡 Загружаем страницу подтем через AJAX...');
                
                const contentContainer = document.querySelector('.content');
                if (!contentContainer) {
                    console.log('❌ Content container не найден, используем browser navigation');
                    window.location.href = url;
                    return;
                }
                
                // Показываем индикатор загрузки
                contentContainer.style.opacity = '0.7';
                
                const response = await fetch(url, {
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });
                
                if (response.ok) {
                    const html = await response.text();
                    
                    // Парсим HTML и извлекаем контент
                    const parser = new DOMParser();
                    const doc = parser.parseFromString(html, 'text/html');
                    const newContent = doc.querySelector('.content');
                    
                    if (newContent) {
                        // Плавно заменяем контент
                        setTimeout(() => {
                            contentContainer.innerHTML = newContent.innerHTML;
                            contentContainer.style.opacity = '1';
                            
                            // Обновляем URL в браузере
                            window.history.pushState({}, '', url);
                            
                            // Обновляем активную навигацию (главная страница)
                            const navItems = document.querySelectorAll('.navigation .list');
                            navItems.forEach(item => {
                                item.classList.remove('active');
                                if (item.getAttribute('data-href') === '/') {
                                    item.classList.add('active');
                                }
                            });
                            
                            // Загружаем скрипт для страницы подтем
                            if (window.loadPageSpecificScripts) {
                                window.loadPageSpecificScripts(url);
                            }
                            
                            console.log('✅ Успешно вернулись на страницу подтем');
                        }, 200);
                    } else {
                        console.log('❌ Новый контент не найден, используем browser navigation');
                        window.location.href = url;
                    }
                } else {
                    console.log('❌ AJAX запрос не удался, используем browser navigation');
                    window.location.href = url;
                }
            } catch (error) {
                console.error('❌ Ошибка при AJAX навигации:', error);
                window.location.href = url;
            }
        }
    }

    /**
     * Глобальная переменная для TaskManager
     */
    let taskManager = null;

    /**
     * Инициализация при загрузке страницы
     */
    function initializeTaskManager() {
        console.log('📄 Инициализация TaskManager...');
        console.log('📄 Найдено элементов .task-item:', document.querySelectorAll('.task-item').length);
        console.log('📄 Найдено элементов .answer-option:', document.querySelectorAll('.answer-option').length);
        
        if (taskManager) {
            console.log('⚠️ TaskManager уже инициализирован');
            return;
        }
        
        taskManager = new TaskManager();
        window.taskManager = taskManager;
        
    }

    // Инициализация при загрузке DOM
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeTaskManager);
    } else {
        initializeTaskManager();
    }

    /**
     * Глобальная функция для совместимости с inline обработчиками
     * @param {HTMLElement} button - Кнопка ответа
     * @param {string} selectedAnswer - Выбранный ответ
     * @param {string} correctAnswer - Правильный ответ
     * @param {string} explanation - Объяснение
     */
    function selectAnswer(button, selectedAnswer, correctAnswer, explanation) {
        console.log('🔧 Вызов selectAnswer (устаревший метод)');
        if (taskManager && taskManager.isInitialized) {
            const event = {
                preventDefault: () => {},
                stopPropagation: () => {},
                currentTarget: button
            };
            taskManager.handleAnswerSelection(event);
        } else {
            console.error('❌ TaskManager не инициализирован');
        }
    }

    /**
     * Глобальная функция для перехода назад со страницы задач
     */
    function goBackFromTasks() {
        console.log('🔧 Вызов goBackFromTasks');
        if (taskManager) {
            taskManager.goBack();
        } else {
            console.error('❌ TaskManager не найден');
            window.history.back();
        }
    }
    
    /**
     * Глобальная функция для переинициализации обработчиков кнопки "Назад"
     */
    function reinitializeBackButton() {
        console.log('🔧 Глобальная reinitializeBackButton() вызвана');
        console.log('🔍 TaskManager существует:', !!taskManager);
        console.log('🔍 Текущий URL:', window.location.href);
        
        if (taskManager) {
            console.log('🔍 TaskManager инициализирован:', taskManager.isInitialized);
            taskManager.reinitializeBackButton();
        } else {
            console.log('⚠️ TaskManager не найден, создаем новый...');
            initializeTaskManager();
        }
        
        console.log('✅ Глобальная reinitializeBackButton() завершена');
    }

    // Функция для имитации Telegram WebApp в браузере (для тестирования)
    function mockTelegramWebApp() {
        const urlParams = new URLSearchParams(window.location.search);
        const mockInitData = urlParams.get('tgWebAppData');
        
        if (mockInitData) {
            console.log('🔧 ТЕСТОВЫЙ РЕЖИМ: Имитируем Telegram WebApp');
            
            // Создаем mock объект window.Telegram.WebApp
            window.Telegram = {
                WebApp: {
                    initData: mockInitData,
                    initDataUnsafe: {
                        user: {
                            id: 975113235, // ID пользователя Mr_Fulani
                            first_name: 'Mr',
                            last_name: 'Fulani',
                            username: 'Mr_Fulani'
                        }
                    },
                    ready: function() {
                        console.log('🔧 Mock Telegram WebApp ready');
                    },
                    expand: function() {
                        console.log('🔧 Mock Telegram WebApp expand');
                    }
                }
            };
            
            console.log('✅ Mock Telegram WebApp создан');
            return true;
        }
        
        return false;
    }

    // Экспортируем функции глобально
    window.goBackFromTasks = goBackFromTasks;
    window.reinitializeBackButton = reinitializeBackButton;
    window.selectAnswer = selectAnswer;
}