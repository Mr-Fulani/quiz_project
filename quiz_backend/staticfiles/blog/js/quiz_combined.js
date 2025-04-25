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
                // Ограничиваем координаты в пределах canvas
                dv.X1 = Math.max(0, Math.min(dv.X1, context.canvas.width / window.devicePixelRatio));
                dv.Y1 = Math.max(0, Math.min(dv.Y1, context.canvas.height / window.devicePixelRatio));
            }

            var r = new Vector(refv.X1, refv.Y1, dv.X1, dv.Y1);

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

    Circle(context, p, lR) {
        context.beginPath();
        context.arc(p.X1 + Math.random() * 10 * lR, p.Y1 + Math.random() * 10 * lR, 8, 0, 2 * Math.PI, false);
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
        lightningCanvas.style.width = '100vw';
        lightningCanvas.style.height = '100vh';
        lightningCanvas.style.pointerEvents = 'none';
        lightningCanvas.style.zIndex = '9999';
        lightningCanvas.style.display = 'none';
        document.body.appendChild(lightningCanvas);
    }

    // Устанавливаем размеры canvas с учетом Retina
    function updateCanvasSize() {
        lightningCanvas.width = window.innerWidth * window.devicePixelRatio;
        lightningCanvas.height = window.innerHeight * window.devicePixelRatio;
        lightningCanvas.style.width = window.innerWidth + 'px';
        lightningCanvas.style.height = window.innerHeight + 'px';
        ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
        console.log(`Canvas resized to ${lightningCanvas.width}x${lightningCanvas.height}`);
    }

    updateCanvasSize();
    const ctx = lightningCanvas.getContext('2d');

    // Конфигурация молнии
    const lightningConfig = {
        Segments: 40,
        Threshold: 0.5,
        Width: 2.0,
        Color: "white",
        Blur: 15,
        BlurColor: "white",
        Alpha: 1,
        GlowColor: "#0000FF",
        GlowWidth: 50,
        GlowBlur: 120,
        GlowAlpha: 40
    };

    const lightning = new Lightning(lightningConfig);

    // Точки начала молний
    let lightningPoints = [];

    function updateLightningPoints() {
        lightningPoints = [
            new Vector(0, 0, 0, 0),
            new Vector(0, 0, lightningCanvas.width / window.devicePixelRatio, 0),
            new Vector(0, 0, 0, lightningCanvas.height / window.devicePixelRatio),
            new Vector(0, 0, lightningCanvas.width / window.devicePixelRatio, lightningCanvas.height / window.devicePixelRatio),
            new Vector(0, 0, lightningCanvas.width / window.devicePixelRatio / 2, 0),
            new Vector(0, 0, 0, lightningCanvas.height / window.devicePixelRatio / 2),
            new Vector(0, 0, lightningCanvas.width / window.devicePixelRatio, lightningCanvas.height / window.devicePixelRatio / 2),
            new Vector(0, 0, lightningCanvas.width / window.devicePixelRatio / 2, lightningCanvas.height / window.devicePixelRatio)
        ];
    }

    updateLightningPoints();

    // Обновление размеров canvas
    window.addEventListener('resize', function() {
        updateCanvasSize();
        updateLightningPoints();
    });

    // Создаём объекты Audio
    const thunderSound = new Audio('/static/blog/sounds/thunder.mp3');
    thunderSound.preload = 'auto';
    thunderSound.volume = 0.3; // Исправлено с 0.3 на 0.7

    const successSound = new Audio('/static/blog/sounds/success.mp3');
    successSound.preload = 'auto';
    successSound.volume = 0.3; // Исправлено с 0.3 на 0.7

    // Функция проигрывания звука с обработкой ошибок
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

    // Функция показа эффекта молнии со звуком (неправильный ответ)
    window.showLightningEffect = function(element) {
        console.log('Showing lightning effect for', element);

        const rect = element.getBoundingClientRect();
        const scrollX = window.scrollX || window.pageXOffset;
        const scrollY = window.scrollY || window.pageYOffset;
        const targetX = Math.max(0, Math.min(rect.left + rect.width / 2 + scrollX, lightningCanvas.width / window.devicePixelRatio));
        const targetY = Math.max(0, Math.min(rect.top + rect.height / 2 + scrollY, lightningCanvas.height / window.devicePixelRatio));
        const target = new Vector(0, 0, targetX, targetY);

        lightningCanvas.style.display = 'block';
        lightningCanvas.style.opacity = '1';

        playSound(thunderSound);

        let frames = 0;
        const maxFrames = 40;

        function animate() {
            ctx.clearRect(0, 0, lightningCanvas.width, lightningCanvas.height);
            ctx.fillStyle = 'rgba(0,0,0,0.4)';
            ctx.fillRect(0, 0, lightningCanvas.width, lightningCanvas.height);

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
        element.classList.add('incorrect');

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

    // Универсальный обработчик событий для ответов
    function setupAnswerHandlers() {
        const answerOptions = document.querySelectorAll('.answer-option');
        if (answerOptions.length > 0) {
            console.log('Answer options found:', answerOptions.length);

            answerOptions.forEach(option => {
                option.removeEventListener('click', handleAnswerSelection);
                option.removeEventListener('touchend', handleAnswerSelection);
                option.addEventListener('click', handleAnswerSelection);
                option.addEventListener('touchend', handleAnswerSelection);
            });
        } else {
            console.log('No answer options found');
        }
    }

    // Функция обработки выбора ответа
    function handleAnswerSelection(event) {
        event.preventDefault();

        const option = this;
        console.log('Option selected:', option.dataset.answer, 'Correct:', option.dataset.correct);
        const isCorrect = option.dataset.correct === 'true';

        const parent = option.parentElement;
        parent.querySelectorAll('.answer-option').forEach(opt => {
            opt.style.pointerEvents = 'none';
            opt.classList.remove('active');
        });

        option.classList.add('active');

        if (!isCorrect) {
            showLightningEffect(option);
        } else {
            showConfetti(option);
        }
    }

    // Инициализируем обработчики сразу
    setupAnswerHandlers();

    // Перепривязываем обработчики при динамической загрузке
    document.addEventListener('DOMContentLoaded', setupAnswerHandlers);
    document.addEventListener('page:loaded', setupAnswerHandlers);
    document.addEventListener('turbolinks:load', setupAnswerHandlers);
});