/**
 * Главный скрипт для квиза, объединяющий эффекты молнии, конфетти и обработку ответов.
 * Включает модальное окно для варианта "Я не знаю, но хочу узнать" и AJAX для статистики.
 */
console.log('Quiz Combined JS Loading...');

/**
 * Класс для работы с векторами.
 */
class Vector {
    /**
     * @param {number} x - Начальная координата X.
     * @param {number} y - Начальная координата Y.
     * @param {number} x1 - Конечная координата X.
     * @param {number} y1 - Конечная координата Y.
     */
    constructor(x, y, x1, y1) {
        this.X = x;
        this.Y = y;
        this.X1 = x1;
        this.Y1 = y1;
    }

    /** @returns {number} Разница по X. */
    dX() { return this.X1 - this.X; }

    /** @returns {number} Разница по Y. */
    dY() { return this.Y1 - this.Y; }

    /** @returns {number} Длина вектора. */
    Length() {
        return Math.sqrt(Math.pow(this.dX(), 2) + Math.pow(this.dY(), 2));
    }

    /**
     * Умножает вектор на коэффициент.
     * @param {number} n - Коэффициент умножения.
     * @returns {Vector} Новый вектор.
     */
    Multiply(n) {
        return new Vector(this.X, this.Y, this.X + this.dX() * n, this.Y + this.dY() * n);
    }
}

/**
 * Класс для создания эффекта молнии.
 */
class Lightning {
    /**
     * @param {Object} c - Конфигурация молнии.
     */
    constructor(c) {
        this.config = c;
    }

    /**
     * Отрисовывает молнию.
     * @param {CanvasRenderingContext2D} context - Контекст canvas.
     * @param {Vector} from - Начальная точка.
     * @param {Vector} to - Конечная точка.
     */
    Cast(context, from, to) {
        context.save();
        if (!from || !to) { return; }

        const v = new Vector(from.X1, from.Y1, to.X1, to.Y1);
        if (this.config.Threshold && v.Length() > context.canvas.width * this.config.Threshold) {
            return;
        }

        const vLen = v.Length();
        let refv = from;
        const lR = (vLen / context.canvas.width);
        const segments = Math.floor(this.config.Segments * lR);
        const l = vLen / segments;

        for (let i = 1; i <= segments; i++) {
            let dv = v.Multiply((1 / segments) * i);
            if (i != segments) {
                dv.Y1 += l * Math.random();
                dv.X1 += l * Math.random();
            }

            const r = new Vector(refv.X1, refv.Y1, dv.X1, dv.Y1);

            this.Line(context, r, {
                Color: this.config.GlowColor,
                Width: this.config.GlowWidth * lR * 1.5,
                Blur: this.config.GlowBlur * lR,
                BlurColor: this.config.GlowColor,
                Alpha: this.Random(this.config.GlowAlpha, this.config.GlowAlpha * 2) / 100
            });

            this.Line(context, r, {
                Color: this.config.Color,
                Width: this.config.Width * 1.5,
                Blur: this.config.Blur,
                BlurColor: this.config.BlurColor,
                Alpha: this.config.Alpha
            });

            refv = r;
        }

        this.Circle(context, to, lR);
        this.Circle(context, from, lR);

        context.restore();
    }

    /**
     * Рисует круг в точке.
     * @param {CanvasRenderingContext2D} context - Контекст canvas.
     * @param {Vector} p - Точка.
     * @param {number} lR - Коэффициент масштаба.
     */
    Circle(context, p, lR) {
        context.beginPath();
        context.arc(p.X1 + Math.random() * 10 * lR, p.Y1 + Math.random() * 10 * lR, 8, 0, 2 * Math.PI, false);
        context.fillStyle = 'white';
        context.shadowBlur = 100;
        context.shadowColor = "#2319FF";
        context.fill();
    }

    /**
     * Рисует линию.
     * @param {CanvasRenderingContext2D} context - Контекст canvas.
     * @param {Vector} v - Вектор.
     * @param {Object} c - Конфигурация линии.
     */
    Line(context, v, c) {
        context.beginPath();
        context.strokeStyle = c.Color;
        context.lineWidth = c.Width;
        context.moveTo(v.X, v.Y);
        context.lineTo(v.X1, v.Y1);
        context.globalAlpha = c.Alpha;
        context.shadowBlur = c.Blur;
        context.shadowColor = c.BlurColor;
        context.stroke();
    }

    /**
     * Генерирует случайное число.
     * @param {number} min - Минимум.
     * @param {number} max - Максимум.
     * @returns {number} Случайное число.
     */
    Random(min, max) {
        return Math.floor(Math.random() * (max - min)) + min;
    }
}

/**
 * Инициализация анимации, звука и модального окна.
 */
document.addEventListener('DOMContentLoaded', function() {
    console.log('Initializing lightning effect');

    // Проверяем и создаем canvas
    let lightningCanvas = document.getElementById('lightning-canvas');
    if (!lightningCanvas) {
        lightningCanvas = document.createElement('canvas');
        lightningCanvas.id = 'lightning-canvas';
        lightningCanvas.style.position = 'fixed';
        lightningCanvas.style.top = '0';
        lightningCanvas.style.left = '0';
        lightningCanvas.style.width = '100vw';
        lightningCanvas.style.height = '100vh';
        lightningCanvas.style.pointerEvents = 'none';
        lightningCanvas.style.zIndex = '9999';
        lightningCanvas.style.display = 'none';
        document.body.appendChild(lightningCanvas);
    }

    /**
     * Обновляет размеры canvas.
     */
    function updateCanvasSize() {
        lightningCanvas.width = window.innerWidth;
        lightningCanvas.height = window.innerHeight;
        console.log(`Canvas resized to ${lightningCanvas.width}x${lightningCanvas.height}`);
    }

    updateCanvasSize();
    const ctx = lightningCanvas.getContext('2d');

    // Конфигурация молнии
    const lightningConfig = {
        Segments: 35,
        Threshold: 0.8,
        Width: 2.5,
        Color: "white",
        Blur: 15,
        BlurColor: "white",
        Alpha: 0.9,
        GlowColor: "#2266FF",
        GlowWidth: 45,
        GlowBlur: 100,
        GlowAlpha: 40
    };

    const lightning = new Lightning(lightningConfig);

    // Точки начала молний
    let lightningPoints = [];

    /**
     * Обновляет точки начала молний.
     */
    function updateLightningPoints() {
        lightningPoints = [
            new Vector(0, 0, 0, 0),
            new Vector(0, 0, lightningCanvas.width, 0),
            new Vector(0, 0, 0, lightningCanvas.height),
            new Vector(0, 0, lightningCanvas.width, lightningCanvas.height),
            new Vector(0, 0, lightningCanvas.width / 2, 0),
            new Vector(0, 0, 0, lightningCanvas.height / 2),
            new Vector(0, 0, lightningCanvas.width, lightningCanvas.height / 2),
            new Vector(0, 0, lightningCanvas.width / 2, lightningCanvas.height)
        ];
    }

    updateLightningPoints();

    window.addEventListener('resize', function() {
        updateCanvasSize();
        updateLightningPoints();
    });

    // Аудио
    const thunderSound = new Audio('/static/blog/sounds/thunder.mp3');
    thunderSound.preload = 'auto';
    thunderSound.volume = 0.3;

    const successSound = new Audio('/static/blog/sounds/success.mp3');
    successSound.preload = 'auto';
    successSound.volume = 0.3;

    /**
     * Проигрывает звук.
     * @param {HTMLAudioElement} sound - Аудио элемент.
     */
    function playSound(sound) {
        sound.currentTime = 0;
        sound.play().catch(error => {
            console.error('Error playing sound:', error);
            document.body.addEventListener('touchstart', function soundTrigger() {
                sound.play().catch(e => console.error('Still cannot play sound:', e));
                document.body.removeEventListener('touchstart', soundTrigger);
            }, { once: true });
        });
    }

    /**
     * Показывает эффект молнии для неправильного ответа.
     * @param {HTMLElement} element - Элемент ответа.
     */
    window.showLightningEffect = function(element) {
        console.log('Showing balanced lightning effect for mobile');

        const rect = element.getBoundingClientRect();
        const targetX = rect.left + rect.width / 2;
        const targetY = rect.top + rect.height / 2;
        const target = new Vector(0, 0, targetX, targetY);

        lightningCanvas.style.display = 'block';
        lightningCanvas.style.opacity = '1';

        const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
        const isSmallScreen = window.innerWidth < 768;

        let frames = 0;
        const maxFrames = isMobile ? 45 : 40;

        let customLightningPoints = [];

        if (isMobile || isSmallScreen) {
            customLightningPoints = [
                new Vector(0, 0, targetX - 50, 0),
                new Vector(0, 0, targetX + 50, 0),
                new Vector(0, 0, targetX, 0),
                new Vector(0, 0, targetX - 50, lightningCanvas.height),
                new Vector(0, 0, targetX + 50, lightningCanvas.height),
                new Vector(0, 0, targetX, lightningCanvas.height),
                new Vector(0, 0, 0, targetY),
                new Vector(0, 0, lightningCanvas.width, targetY),
                new Vector(0, 0, 0, 0),
                new Vector(0, 0, lightningCanvas.width, lightningCanvas.height)
            ];
        } else {
            customLightningPoints = lightningPoints;
        }

        function animate() {
            ctx.clearRect(0, 0, lightningCanvas.width, lightningCanvas.height);

            ctx.fillStyle = isMobile ? 'rgba(0,0,0,0.4)' : 'rgba(0,0,0,0.3)';
            ctx.fillRect(0, 0, lightningCanvas.width, lightningCanvas.height);

            const numPoints = isMobile ? 3 + Math.floor(Math.random() * 2) : 2;
            const shuffledPoints = [...customLightningPoints].sort(() => 0.5 - Math.random());
            const selectedPoints = shuffledPoints.slice(0, numPoints);

            selectedPoints.forEach(point => {
                const jitterX = (Math.random() - 0.5) * 25;
                const jitterY = (Math.random() - 0.5) * 25;
                const jitteredTarget = new Vector(0, 0, targetX + jitterX, targetY + jitterY);

                lightning.Cast(ctx, point, jitteredTarget);
            });

            frames++;
            if (frames < maxFrames) {
                requestAnimationFrame(animate);
            } else {
                lightningCanvas.style.display = 'none';
            }
        }

        animate();
        element.classList.add('incorrect');
        tryVibrateMultipleMethods();
    };

    /**
     * Показывает эффект конфетти для правильного ответа.
     * @param {HTMLElement} element - Элемент ответа.
     */
    window.showConfetti = function(element) {
        console.log('Showing confetti effect for', element);

        const rect = element.getBoundingClientRect();
        const canvas = lightningCanvas;
        const ctx = canvas.getContext('2d');
        const particles = [];

        const startX = rect.left + rect.width / 2;
        const startY = rect.top + rect.height / 2;

        for (let i = 0; i < 150; i++) {
            particles.push({
                x: startX,
                y: startY,
                speed: Math.random() * 6 + 3,
                angle: Math.random() * 2 * Math.PI,
                size: Math.random() * 6 + 3,
                color: `hsl(${Math.random() * 360}, 100%, 50%)`,
                life: 80
            });
        }

        playSound(successSound);

        function animateConfetti() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            particles.forEach((p, i) => {
                p.x += Math.cos(p.angle) * p.speed;
                p.y += Math.sin(p.angle) * p.speed + 0.1;
                p.life--;

                ctx.fillStyle = p.color;
                ctx.fillRect(p.x, p.y, p.size, p.size);

                if (p.life <= 0) particles.splice(i, 1);
            });

            if (particles.length > 0) requestAnimationFrame(animateConfetti);
            else canvas.style.display = 'none';
        }

        canvas.style.display = 'block';
        canvas.style.opacity = '1';
        animateConfetti();
        element.classList.add('correct');
    };

    /**
     * Показывает правильный ответ, выделяя его зеленым цветом.
     * @param {HTMLElement} taskItem - Элемент задачи.
     */
    function showCorrectAnswer(taskItem) {
        const answers = taskItem.querySelectorAll('.answer-option');
        answers.forEach(btn => {
            if (btn.dataset.correct === 'true') {
                btn.classList.add('correct');
            }
        });
    }

    /**
     * Форматирует текст объяснения: выделяет заголовки, списки и код.
     * @param {string} text - Исходный текст.
     * @returns {string} - Отформатированный HTML.
     */
    function formatExplanation(text) {
        if (!text) return '';
        
        let formatted = text;
        
        // Сначала выделяем код в обратных кавычках (чтобы не трогать его дальше)
        const codeBlocks = [];
        formatted = formatted.replace(/`([^`]+)`/g, (match, code) => {
            const placeholder = `__CODE_${codeBlocks.length}__`;
            codeBlocks.push(`<code>${escapeHtml(code)}</code>`);
            return placeholder;
        });
        
        // Выделяем заголовок "Step-by-step explanation:" или аналогичные
        let title = '';
        formatted = formatted.replace(/^(Step-by-step explanation:|Пошаговое объяснение:|Adım adım açıklama:|شرح خطوة بخطوة:)\s*\n?/im, (match, titleText) => {
            title = `<div class="explanation-title">${escapeHtml(titleText)}</div>`;
            return '';
        });
        
        // Преобразуем нумерованный список (1. текст)
        const lines = formatted.split('\n');
        let inList = false;
        let listItems = [];
        let result = title ? [title] : [];
        
        lines.forEach(line => {
            line = line.trim();
            if (!line) {
                if (inList && listItems.length > 0) {
                    result.push('<ol>' + listItems.join('') + '</ol>');
                    listItems = [];
                    inList = false;
                }
                return;
            }
            
            // Проверяем, является ли строка элементом списка
            const listMatch = line.match(/^(\d+)\.\s+(.+)$/);
            if (listMatch) {
                if (!inList) inList = true;
                let itemText = listMatch[2];
                const itemNumber = listMatch[1]; // Сохраняем номер из текста
                // Восстанавливаем код в элементах списка
                itemText = itemText.replace(/__CODE_(\d+)__/g, (_, idx) => codeBlocks[parseInt(idx)] || '');
                listItems.push(`<li data-number="${itemNumber}">${itemText}</li>`);
            } else {
                if (inList && listItems.length > 0) {
                    result.push('<ol>' + listItems.join('') + '</ol>');
                    listItems = [];
                    inList = false;
                }
                // Восстанавливаем код в обычных строках
                line = line.replace(/__CODE_(\d+)__/g, (_, idx) => codeBlocks[parseInt(idx)] || '');
                result.push(`<p>${line}</p>`);
            }
        });
        
        // Закрываем список, если он остался открытым
        if (inList && listItems.length > 0) {
            result.push('<ol>' + listItems.join('') + '</ol>');
        }
        
        return result.join('');
    }
    
    /**
     * Экранирует HTML для безопасности.
     * @param {string} text - Текст для экранирования.
     * @returns {string} - Экранированный текст.
     */
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Показывает модальное окно с объяснением и предотвращает прокрутку страницы.
     * @param {string} explanation - Текст объяснения.
     */
    function showModal(explanation) {
        let modal = document.querySelector('.modal');
        if (modal) {
            modal.remove();
        }

        // Форматируем текст
        const formattedExplanation = formatExplanation(explanation);

        modal = document.createElement('div');
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content">
                <div class="explanation-text">${formattedExplanation}</div>
            </div>
        `;
        document.body.appendChild(modal);

        // Исправляем нумерацию списков - устанавливаем data-number для всех элементов
        const allOl = modal.querySelectorAll('.explanation-text ol');
        allOl.forEach(ol => {
            const listItems = ol.querySelectorAll('li');
            listItems.forEach((li, index) => {
                // Если data-number уже есть, используем его, иначе устанавливаем порядковый номер
                if (!li.hasAttribute('data-number')) {
                    li.setAttribute('data-number', (index + 1).toString());
                }
            });
        });

        const modalContent = modal.querySelector('.modal-content');
        const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);

        // Предотвращаем прокрутку страницы при открытом модальном окне
        const scrollY = window.scrollY;
        document.body.style.position = 'fixed';
        document.body.style.top = `-${scrollY}px`;
        document.body.style.width = '100%';

        // Обработчик для закрытия модального окна при клике/касании на фон
        const closeModalHandler = (e) => {
            if (e.target === modal) {
                modal.remove();
                // Восстанавливаем прокрутку страницы
                document.body.style.position = '';
                document.body.style.top = '';
                document.body.style.width = '';
                window.scrollTo(0, scrollY);
            }
        };

        // Добавляем обработчики для всех устройств
        modal.addEventListener('click', closeModalHandler);
        if (isMobile) {
            modal.addEventListener('touchstart', closeModalHandler);
        }

        modal.style.display = 'flex';
    }

    /**
     * Пытается активировать вибрацию разными методами.
     */
    function tryVibrateMultipleMethods() {
        console.log("Trying multiple vibration methods");

        if ('vibrate' in navigator) {
            try {
                navigator.vibrate([100, 30, 200, 30, 300]);
                console.log('Standard vibration activated');
                setTimeout(() => {
                    navigator.vibrate(200);
                }, 700);
            } catch (e) {
                console.error('Error with standard vibration:', e);
            }
        }

        setTimeout(() => {
            try {
                if ('vibrate' in navigator) {
                    navigator.vibrate(300);
                    console.log('Delayed vibration activated');
                }
            } catch (e) {
                console.error('Error with delayed vibration:', e);
            }
        }, 100);

        try {
            if (window.navigator && window.navigator.vibrate) {
                window.navigator.vibrate([150, 50, 150]);
                console.log('Window navigator vibration activated');
            }
        } catch (e) {
            console.error('Error with window.navigator vibration:', e);
        }

        try {
            const navAny = navigator;
            if (navAny.mozVibrate) {
                navAny.mozVibrate([100, 50, 200]);
                console.log('Mozilla vibration activated');
            } else if (navAny.webkitVibrate) {
                navAny.webkitVibrate([100, 50, 200]);
                console.log('Webkit vibration activated');
            }
        } catch (e) {
            console.error('Error with prefixed vibration:', e);
        }
    }

    /**
     * Отправляет ответ через AJAX.
     * @param {string} submitUrl - URL для отправки ответа.
     * @param {string} answer - Выбранный ответ.
     * @returns {Promise<Object>} Ответ сервера.
     */
    async function submitAnswer(submitUrl, answer) {
        try {
            const response = await fetch(submitUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: `answer=${encodeURIComponent(answer)}`
            });
            const data = await response.json();
            console.log('Answer submitted:', data);
            return data;
        } catch (error) {
            console.error('Error submitting answer:', error);
            return { error: 'Failed to submit answer' };
        }
    }

    /**
     * Получает значение cookie.
     * @param {string} name - Имя cookie.
     * @returns {string|null} Значение cookie или null.
     */
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    // Список вариантов "Я не знаю, но хочу узнать" на всех языках
    const dontKnowOptions = [
        "Я не знаю, но хочу узнать",
        "I don't know, but I want to learn",


    ];

    /**
     * Устанавливает обработчики событий для вариантов ответа и добавляет класс dont-know-option.
     */
    function setupAnswerHandlers() {
        const answerOptions = document.querySelectorAll('.answer-option');
        if (answerOptions.length > 0) {
            console.log('Answer options found:', answerOptions.length);

            answerOptions.forEach(option => {
                // Удаляем существующие обработчики
                option.removeEventListener('click', handleAnswerSelection);
                option.removeEventListener('touchend', handleTouchEnd);
                option.removeEventListener('touchstart', handleTouchStart);
                option.removeEventListener('touchmove', handleTouchMove);

                // Добавляем класс dont-know-option, если ответ в списке
                const isDontKnowOption = dontKnowOptions.includes(option.dataset.answer);
                if (isDontKnowOption) {
                    option.classList.add('dont-know-option');
                }

                // Для варианта "Я не знаю" добавляем обработчик для повторного показа объяснения
                if (isDontKnowOption) {
                    const showExplanationHandler = (e) => {
                        const taskItem = option.closest('.task-item');
                        if (taskItem && taskItem.dataset.solved === 'true') {
                            // Если задача уже решена, показываем только модальное окно с объяснением
                            e.preventDefault();
                            e.stopPropagation();
                            e.stopImmediatePropagation();
                            const explanation = taskItem.dataset.explanation || 'No explanation available.';
                            showModal(explanation);
                            return false;
                        }
                    };
                    // Добавляем обработчик с флагом capture для приоритета
                    option.addEventListener('click', showExplanationHandler, true);
                    option.addEventListener('touchend', showExplanationHandler, true);
                }

                // Добавляем новые обработчики
                option.addEventListener('click', handleAnswerSelection);
                option.addEventListener('touchstart', handleTouchStart);
                option.addEventListener('touchmove', handleTouchMove);
                option.addEventListener('touchend', handleTouchEnd);
            });
        } else {
            console.log('No answer options found');
        }
    }

    // Обработка касаний
    let touchStartTime = 0;
    let touchStartY = 0;
    let isTouchMoved = false;
    const touchThreshold = 10;
    const touchDelay = 120;

    /**
     * Обрабатывает начало касания.
     * @param {TouchEvent} event - Событие касания.
     */
    function handleTouchStart(event) {
        touchStartTime = Date.now();
        touchStartY = event.touches[0].clientY;
        isTouchMoved = false;
    }

    /**
     * Обрабатывает движение касания.
     * @param {TouchEvent} event - Событие касания.
     */
    function handleTouchMove(event) {
        if (Math.abs(event.touches[0].clientY - touchStartY) > touchThreshold) {
            isTouchMoved = true;
        }
    }

    /**
     * Обрабатывает окончание касания.
     * @param {TouchEvent} event - Событие касания.
     */
    function handleTouchEnd(event) {
        const touchDuration = Date.now() - touchStartTime;

        if (!isTouchMoved && touchDuration < touchDelay) {
            event.preventDefault();
            setTimeout(() => {
                if (!isTouchMoved) {
                    handleAnswerSelection.call(this, event);
                }
            }, 50);
        }
    }

    // Проверяем, запущено ли приложение в Telegram Web App
    const isTelegramWebApp = window.Telegram && window.Telegram.WebApp;
    if (isTelegramWebApp) {
        console.log('Running in Telegram Web App');
        window.Telegram.WebApp.ready();
    }

    /**
     * Проверяет авторизацию пользователя через AJAX-запрос.
     * @returns {Promise<boolean>} Возвращает true, если пользователь авторизован, иначе false.
     */
    async function checkUserAuth() {
        try {
            const response = await fetch(window.location.origin + '/api/check-auth/', {
                method: 'GET',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken')
                }
            });
            const data = await response.json();
            return data.is_authenticated;
        } catch (error) {
            console.error('Error checking auth status:', error);
            return false;
        }
    }

    async function handleAnswerSelection(event) {
        /**
         * Обрабатывает выбор ответа пользователем, применяет стили и отправляет ответ на сервер.
         * Если пользователь не авторизован, открывает модальное окно входа.
         *
         * @param {Event} event - Событие клика по варианту ответа.
         */
        event.preventDefault();
        event.stopPropagation();
        const option = this;
        const taskItem = option.closest('.task-item');

        console.log('Task ID:', taskItem.dataset.taskId, 'Answer:', option.dataset.answer);

        // Проверка авторизации
        const isAuthenticated = await checkUserAuth();
        if (!isAuthenticated) {
            console.log('User is not authenticated, opening login modal');
            const loginModal = document.getElementById('login-modal');
            if (loginModal) {
                // Получаем текущий URL с параметром страницы
                const currentUrl = window.location.href;
                const loginForm = loginModal.querySelector('form');
                if (loginForm) {
                    // Удаляем существующее поле next, если есть
                    const existingNext = loginForm.querySelector('input[name="next"]');
                    if (existingNext) existingNext.remove();
                    // Добавляем поле next с текущим URL
                    const nextInput = document.createElement('input');
                    nextInput.type = 'hidden';
                    nextInput.name = 'next';
                    nextInput.value = currentUrl;
                    loginForm.appendChild(nextInput);
                }
                loginModal.classList.add('active');
            } else {
                console.log('Login modal not found - user may need to login through header link');
                // Перенаправляем на страницу логина
                window.location.href = window.location.origin + '/accounts/login/?next=' + encodeURIComponent(window.location.href);
            }
            return;
        }

        if (taskItem.dataset.solved === 'true') {
            console.log('Answer selection blocked: task already solved');
            return;
        }

        const isCorrect = option.dataset.correct === 'true';
        const isDontKnow = option.classList.contains('dont-know-option') || dontKnowOptions.includes(option.dataset.answer);
        const parent = option.parentElement;

        // Фиксируем задачу, но оставляем вариант "Я не знаю" кликабельным для повторного показа объяснения
        parent.querySelectorAll('.answer-option').forEach(opt => {
            const optIsDontKnow = opt.classList.contains('dont-know-option') || dontKnowOptions.includes(opt.dataset.answer);
            // Вариант "Я не знаю" остается кликабельным для повторного показа объяснения
            if (!optIsDontKnow) {
                opt.style.pointerEvents = 'none';
            }
            opt.classList.remove('active');
            opt.classList.add('disabled');
            if (opt === option) {
                opt.classList.add(isCorrect ? 'correct' : 'incorrect');
            }
        });
        option.classList.add('active');
        taskItem.dataset.solved = 'true';

        const submitUrl = taskItem.dataset.submitUrl;
        let explanation = taskItem.dataset.explanation || 'No explanation available.';

        if (submitUrl) {
            try {
                const result = await submitAnswer(submitUrl, option.dataset.answer);
                if (result.error) {
                    console.error('Failed to submit answer:', result.error);
                    alert(`Ошибка: ${result.error}`);
                    // Откатываем фиксацию
                    parent.querySelectorAll('.answer-option').forEach(opt => {
                        opt.style.pointerEvents = 'auto';
                        opt.classList.remove('disabled', 'correct', 'incorrect', 'active');
                    });
                    taskItem.dataset.solved = 'false';
                } else {
                    explanation = result.explanation || explanation;
                    if (isCorrect) {
                        showConfetti(option);
                    } else if (!isDontKnow) {
                        showLightningEffect(option);
                        showCorrectAnswer(taskItem);
                    }
                    // Показываем модальное окно с объяснением всегда
                    showModal(explanation);
                }
            } catch (error) {
                console.error('Submit error:', error);
                alert('Произошла ошибка при отправке ответа.');
                // Откатываем фиксацию
                parent.querySelectorAll('.answer-option').forEach(opt => {
                    opt.style.pointerEvents = 'auto';
                    opt.classList.remove('disabled', 'correct', 'incorrect', 'active');
                });
                taskItem.dataset.solved = 'false';
            }
        }
    }

    setupAnswerHandlers();
    document.addEventListener('DOMContentLoaded', setupAnswerHandlers);
    document.addEventListener('page:loaded', setupAnswerHandlers);
    document.addEventListener('turbolinks:load', setupAnswerHandlers);
});// TEMPORARY COMMENT TO FORCE UPDATE
