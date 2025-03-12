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
                Width: this.config.GlowWidth * lR,
                Blur: this.config.GlowBlur * lR,
                BlurColor: this.config.GlowColor,
                Alpha: this.Random(this.config.GlowAlpha, this.config.GlowAlpha * 2) / 100
            });

            this.Line(context, r, {
                Color: this.config.Color,
                Width: this.config.Width,
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
        context.arc(p.X1 + Math.random() * 10 * lR, p.Y1 + Math.random() * 10 * lR, 5, 0, 2 * Math.PI, false);
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

    // Создаём глобальный canvas для молний и конфетти
    const lightningCanvas = document.createElement('canvas');
    lightningCanvas.id = 'lightning-canvas';
    lightningCanvas.style.position = 'fixed';
    lightningCanvas.style.top = '0';
    lightningCanvas.style.left = '0';
    lightningCanvas.style.width = '100%';
    lightningCanvas.style.height = '100%';
    lightningCanvas.style.pointerEvents = 'none';
    lightningCanvas.style.zIndex = '1000';
    lightningCanvas.style.display = 'none';
    document.body.appendChild(lightningCanvas);

    lightningCanvas.width = window.innerWidth;
    lightningCanvas.height = window.innerHeight;
    const ctx = lightningCanvas.getContext('2d');

    // Конфигурация молнии
    const lightningConfig = {
        Segments: 40,
        Threshold: 0.5,
        Width: 1.5,
        Color: "white",
        Blur: 10,
        BlurColor: "white",
        Alpha: 1,
        GlowColor: "#0000FF",
        GlowWidth: 40,
        GlowBlur: 100,
        GlowAlpha: 30
    };

    const lightning = new Lightning(lightningConfig);

    // Точки начала молний
    const lightningPoints = [
        new Vector(0, 0, 0, 0),
        new Vector(0, 0, lightningCanvas.width, 0),
        new Vector(0, 0, 0, lightningCanvas.height),
        new Vector(0, 0, lightningCanvas.width, lightningCanvas.height),
        new Vector(0, 0, lightningCanvas.width / 2, 0),
        new Vector(0, 0, 0, lightningCanvas.height / 2),
        new Vector(0, 0, lightningCanvas.width, lightningCanvas.height / 2),
        new Vector(0, 0, lightningCanvas.width / 2, lightningCanvas.height)
    ];

    // Обновление размеров canvas
    window.addEventListener('resize', function() {
        lightningCanvas.width = window.innerWidth;
        lightningCanvas.height = window.innerHeight;
        lightningPoints[1] = new Vector(0, 0, lightningCanvas.width, 0);
        lightningPoints[2] = new Vector(0, 0, 0, lightningCanvas.height);
        lightningPoints[3] = new Vector(0, 0, lightningCanvas.width, lightningCanvas.height);
        lightningPoints[4] = new Vector(0, 0, lightningCanvas.width / 2, 0);
        lightningPoints[5] = new Vector(0, 0, 0, lightningCanvas.height / 2);
        lightningPoints[6] = new Vector(0, 0, lightningCanvas.width, lightningCanvas.height / 2);
        lightningPoints[7] = new Vector(0, 0, lightningCanvas.width / 2, lightningCanvas.height);
    });

    // Создаём объекты Audio
    const thunderSound = new Audio('/static/blog/sounds/thunder.mp3');
    thunderSound.preload = 'auto';
    thunderSound.volume = 0.5;

    const successSound = new Audio('/static/blog/sounds/success.mp3');
    successSound.preload = 'auto';
    successSound.volume = 0.5;

    // Функция показа эффекта молнии со звуком (неправильный ответ)
    window.showLightningEffect = function(element) {
        console.log('Showing lightning effect for', element);

        const rect = element.getBoundingClientRect();
        const targetX = rect.left + rect.width / 2;
        const targetY = rect.top + rect.height / 2;
        const target = new Vector(0, 0, targetX, targetY);

        lightningCanvas.style.display = 'block';

        // Проигрываем звук грома
        thunderSound.currentTime = 0;
        thunderSound.play().catch(error => {
            console.error('Error playing thunder sound:', error);
        });

        let frames = 0;
        const maxFrames = 30;

        function animate() {
            ctx.clearRect(0, 0, lightningCanvas.width, lightningCanvas.height);
            ctx.fillStyle = 'rgba(0,0,0,0.3)';
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

        // Создаём частицы конфетти
        for (let i = 0; i < 100; i++) {
            particles.push({
                x: startX,
                y: startY,
                speed: Math.random() * 5 + 2,
                angle: Math.random() * 2 * Math.PI, // Во все стороны
                size: Math.random() * 5 + 2,
                color: `hsl(${Math.random() * 360}, 100%, 50%)`,
                life: 60
            });
        }

        // Проигрываем звук успеха
        successSound.currentTime = 0;
        successSound.play().catch(error => {
            console.error('Error playing success sound:', error);
        });

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
        animateConfetti();
    };

    // Привязка к answer-option
    const answerOptions = document.querySelectorAll('.answer-option');
    if (answerOptions.length > 0) {
        console.log('Answer options found:', answerOptions.length);
        answerOptions.forEach(option => {
            option.addEventListener('click', function() {
                console.log('Option clicked:', this.dataset.answer, 'Correct:', this.dataset.correct);
                const isCorrect = this.dataset.correct === 'true';

                // Очистка предыдущих эффектов
                option.parentElement.querySelectorAll('.answer-option').forEach(opt => {
                    opt.classList.remove('correct-answer', 'shake');
                });

                if (!isCorrect) {
                    showLightningEffect(this);
                    this.classList.add('shake');
                    setTimeout(() => this.classList.remove('shake'), 500);

                    // Вибрация (только для мобильных устройств)
                    if (navigator.vibrate) {
                        navigator.vibrate(200);
                    }
                } else {
                    showConfetti(this); // Конфетти для правильного ответа
                    this.classList.add('correct-answer');
                    setTimeout(() => this.classList.remove('correct-answer'), 1000);
                }
            });
        });
    } else {
        console.log('No answer options found');
    }
});