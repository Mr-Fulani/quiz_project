console.log('Quiz Combined JS Loading...');

// Класс Vector
class Vector {
    constructor(x, y, x1, y1) {
        this.X = x;
        this.Y = y;
        this.X1 = x1;
        this.Y1 = y1;
    }

    dX() { return this.X1 - this.X; }
    dY() { return this.Y1 - this.Y; }

    Length() {
        return Math.sqrt(Math.pow(this.dX(), 2) + Math.pow(this.dY(), 2));
    }

    Multiply(n) {
        return new Vector(this.X, this.Y, this.X + this.dX() * n, this.Y + this.dY() * n);
    }
}

// Класс Lightning
class Lightning {
    constructor(c) {
        this.config = c;
    }

    Cast(context, from, to) {
        context.save();
        if (!from || !to) { return; }

        var v = new Vector(from.X1, from.Y1, to.X1, to.Y1);
        if (this.config.Threshold && v.Length() > context.canvas.width * this.config.Threshold) {
            return;
        }

        var vLen = v.Length();
        var refv = from;
        var lR = (vLen / context.canvas.width);
        var segments = Math.floor(this.config.Segments * lR);
        var l = vLen / segments;

        for (let i = 1; i <= segments; i++) {
            var dv = v.Multiply((1 / segments) * i);
            if (i != segments) {
                dv.Y1 += l * Math.random();
                dv.X1 += l * Math.random();
            }

            var r = new Vector(refv.X1, refv.Y1, dv.X1, dv.Y1);

            this.Line(context, r, {
                Color: this.config.GlowColor,
                Width: this.config.GlowWidth * lR * 1.5, // Увеличиваем ширину для мобильных
                Blur: this.config.GlowBlur * lR,
                BlurColor: this.config.GlowColor,
                Alpha: this.Random(this.config.GlowAlpha, this.config.GlowAlpha * 2) / 100
            });

            this.Line(context, r, {
                Color: this.config.Color,
                Width: this.config.Width * 1.5, // Увеличиваем ширину для мобильных
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

    Circle(context, p, lR) {
        context.beginPath();
        context.arc(p.X1 + Math.random() * 10 * lR, p.Y1 + Math.random() * 10 * lR, 8, 0, 2 * Math.PI, false); // Увеличиваем радиус
        context.fillStyle = 'white';
        context.shadowBlur = 100;
        context.shadowColor = "#2319FF";
        context.fill();
    }

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

    Random(min, max) {
        return Math.floor(Math.random() * (max - min)) + min;
    }
}

// Инициализация анимации и звука
document.addEventListener('DOMContentLoaded', function() {
    console.log('Initializing lightning effect');

    // Проверяем, существует ли уже canvas
    let lightningCanvas = document.getElementById('lightning-canvas');
    if (!lightningCanvas) {
        // Создаём глобальный canvas для молний и конфетти
        lightningCanvas = document.createElement('canvas');
        lightningCanvas.id = 'lightning-canvas';
        lightningCanvas.style.position = 'fixed';
        lightningCanvas.style.top = '0';
        lightningCanvas.style.left = '0';
        lightningCanvas.style.width = '100vw'; // Используем vw вместо %
        lightningCanvas.style.height = '100vh'; // Используем vh вместо %
        lightningCanvas.style.pointerEvents = 'none';
        lightningCanvas.style.zIndex = '9999'; // Увеличиваем z-index
        lightningCanvas.style.display = 'none';
        document.body.appendChild(lightningCanvas);
    }

    // Устанавливаем размеры canvas в пикселях
    function updateCanvasSize() {
        lightningCanvas.width = window.innerWidth;
        lightningCanvas.height = window.innerHeight;
        console.log(`Canvas resized to ${lightningCanvas.width}x${lightningCanvas.height}`);
    }

    updateCanvasSize();
    const ctx = lightningCanvas.getContext('2d');

    // Конфигурация молнии - усилили яркость и ширину для мобильных
    const lightningConfig = {
        Segments: 40,
        Threshold: 0.5,
        Width: 2.0, // Увеличено
        Color: "white",
        Blur: 15, // Увеличено
        BlurColor: "white",
        Alpha: 1,
        GlowColor: "#0000FF",
        GlowWidth: 50, // Увеличено
        GlowBlur: 120, // Увеличено
        GlowAlpha: 40 // Увеличено
    };

    const lightning = new Lightning(lightningConfig);

    // Точки начала молний - будут обновляться при изменении размеров
    let lightningPoints = [];

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

    // Обновление размеров canvas
    window.addEventListener('resize', function() {
        updateCanvasSize();
        updateLightningPoints();
    });

    // Создаём объекты Audio с фоллбэком
    const thunderSound = new Audio('/static/blog/sounds/thunder.mp3');
    thunderSound.preload = 'auto';
    thunderSound.volume = 0.3; // Увеличиваем громкость

    const successSound = new Audio('/static/blog/sounds/success.mp3');
    successSound.preload = 'auto';
    successSound.volume = 0.3; // Увеличиваем громкость

    // Функция проигрывания звука с обработкой ошибок
    function playSound(sound) {
        // Перезагружаем звук если он уже играл
        sound.currentTime = 0;

        // Пытаемся проиграть звук
        sound.play().catch(error => {
            console.error('Error playing sound:', error);
            // Для iOS и некоторых мобильных браузеров требуется взаимодействие с пользователем
            document.body.addEventListener('touchstart', function soundTrigger() {
                sound.play().catch(e => console.error('Still cannot play sound:', e));
                document.body.removeEventListener('touchstart', soundTrigger);
            }, { once: true });
        });
    }

    // Функция показа эффекта молнии со звуком (неправильный ответ)
    window.showLightningEffect = function(element) {
        console.log('Showing lightning effect for', element);

        const rect = element.getBoundingClientRect();
        const targetX = rect.left + rect.width / 2;
        const targetY = rect.top + rect.height / 2;
        const target = new Vector(0, 0, targetX, targetY);

        // Явно задаем display: block и прозрачность
        lightningCanvas.style.display = 'block';
        lightningCanvas.style.opacity = '1';

        // Проигрываем звук грома
        playSound(thunderSound);

        let frames = 0;
        const maxFrames = 40; // Увеличиваем для мобильных

        function animate() {
            ctx.clearRect(0, 0, lightningCanvas.width, lightningCanvas.height);
            ctx.fillStyle = 'rgba(0,0,0,0.4)'; // Увеличиваем непрозрачность фона
            ctx.fillRect(0, 0, lightningCanvas.width, lightningCanvas.height);

            // Чистим и рисуем молнии
            lightningPoints.forEach(point => {
                lightning.Cast(ctx, point, target);
            });

            frames++;
            if (frames < maxFrames) {
                requestAnimationFrame(animate);
            } else {
                lightningCanvas.style.display = 'none';
            }
        }

        animate();

        // Добавляем класс к элементу сразу
        element.classList.add('incorrect');

        // Вибрация для мобильных устройств
        if (navigator.vibrate) {
            navigator.vibrate([100, 50, 100]);
        }
    };

    // Функция показа эффекта конфетти (правильный ответ)
    window.showConfetti = function(element) {
        console.log('Showing confetti effect for', element);

        const rect = element.getBoundingClientRect();
        const canvas = lightningCanvas;
        const ctx = canvas.getContext('2d');
        const particles = [];

        // Начальная позиция — центр элемента
        const startX = rect.left + rect.width / 2;
        const startY = rect.top + rect.height / 2;

        // Создаём больше частиц для мобильных
        for (let i = 0; i < 150; i++) {
            particles.push({
                x: startX,
                y: startY,
                speed: Math.random() * 6 + 3, // Быстрее
                angle: Math.random() * 2 * Math.PI, // Во все стороны
                size: Math.random() * 6 + 3, // Крупнее
                color: `hsl(${Math.random() * 360}, 100%, 50%)`,
                life: 80 // Дольше живут
            });
        }

        // Проигрываем звук успеха
        playSound(successSound);

        function animateConfetti() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            particles.forEach((p, i) => {
                p.x += Math.cos(p.angle) * p.speed;
                p.y += Math.sin(p.angle) * p.speed + 0.1; // Гравитация
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

        // Добавляем класс к элементу сразу
        element.classList.add('correct');
    };

    // Универсальный обработчик событий для ответов (работает для клика и касания)
    function setupAnswerHandlers() {
        const answerOptions = document.querySelectorAll('.answer-option');
        if (answerOptions.length > 0) {
            console.log('Answer options found:', answerOptions.length);

            answerOptions.forEach(option => {
                // Удаляем предыдущие обработчики если они были
                option.removeEventListener('click', handleAnswerSelection);
                option.removeEventListener('touchend', handleAnswerSelection);

                // Добавляем новые обработчики
                option.addEventListener('click', handleAnswerSelection);
                option.addEventListener('touchend', handleAnswerSelection);
            });
        } else {
            console.log('No answer options found');
        }
    }

    // Функция обработки выбора ответа
    function handleAnswerSelection(event) {
        event.preventDefault(); // Предотвращаем дефолтное поведение для touchend

        const option = this;
        console.log('Option selected:', option.dataset.answer, 'Correct:', option.dataset.correct);
        const isCorrect = option.dataset.correct === 'true';

        // Отключаем все варианты ответов в этой группе
        const parent = option.parentElement;
        parent.querySelectorAll('.answer-option').forEach(opt => {
            opt.style.pointerEvents = 'none';
            opt.classList.remove('active'); // Убираем активный класс со всех
        });

        // Добавляем активный класс к выбранному
        option.classList.add('active');

        if (!isCorrect) {
            showLightningEffect(option);
        } else {
            showConfetti(option);
        }
    }

    // Инициализируем обработчики сразу
    setupAnswerHandlers();

    // Перепривязываем обработчики при динамической загрузке контента (например, при пагинации)
    document.addEventListener('DOMContentLoaded', setupAnswerHandlers);
    document.addEventListener('page:loaded', setupAnswerHandlers);

    // Также привязываем к событию загрузки страницы через AJAX, если оно используется
    document.addEventListener('turbolinks:load', setupAnswerHandlers);
});