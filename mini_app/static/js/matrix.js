document.addEventListener('DOMContentLoaded', function() {
    const container = document.querySelector('.matrix-rain');
    if (!container) {
        console.warn('Не найден .matrix-rain');
        return;
    }

    function createDrop() {
        const drop = document.createElement('div');
        drop.className = 'matrix-drop';

        // Случайная позиция по горизонтали
        const left = Math.floor(Math.random() * window.innerWidth);
        drop.style.left = left + 'px';
        drop.style.top = '-20px';

        // Случайный символ
        const symbols = "!@#$%^&*()_+{}[]|;:,.<>?";
        drop.textContent = symbols[Math.floor(Math.random() * symbols.length)];

        // Случайная скорость падения (2..4 секунд)
        const duration = 2 + Math.random() * 2;
        // Если используете цветовую анимацию, добавьте её сюда
        drop.style.animation = `fall ${duration}s linear, colorShift ${duration * 2}s linear`;

        // Начальный случайный оттенок цвета (0..360)
        const hue = Math.floor(Math.random() * 360);  // Полный спектр
        const saturation = 100; // Полная насыщенность
        const lightness = 40 + Math.random() * 20; // Контролируем яркость
        drop.style.color = `hsl(${hue}, ${saturation}%, ${lightness}%)`;
        drop.style.textShadow = `0 0 8px hsl(${hue}, ${saturation}%, ${lightness}%)`;

        container.appendChild(drop);

        // Удаляем каплю по окончании анимации
        setTimeout(() => {
            if (container.contains(drop)) {
                container.removeChild(drop);
            }
        }, duration * 1000);
    }

    // Создаём капли каждые 25 мс (~40 капель/сек)
    setInterval(createDrop, 25);
});