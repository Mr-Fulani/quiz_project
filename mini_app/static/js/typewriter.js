// static/js/typewriter.js

document.addEventListener("DOMContentLoaded", function() {
    console.log("=== Инициализация typewriter.js ===");
    
    const typedTextSpan = document.getElementById("typed-text");
    const cursorSpan = document.getElementById("cursor");
    
    // Создаем аудио объект
    const typingSound = new Audio('/static/audio/typing.mp3');
    typingSound.preload = 'auto';
    typingSound.volume = 0.5;
    
    // Флаг, указывающий, включен ли звук
    let soundEnabled = false;
    
    // Функция для воспроизведения звука
    function playTypingSound() {
        if (!soundEnabled) return;
        
        typingSound.currentTime = 0;
        typingSound.play().catch(error => {
            console.error("Ошибка воспроизведения:", error);
        });
    }
    
    // Массив текстов для печати
    const texts = ["Выбери тему", "Треннеруйся", "Повышай уровень"];
    
    let textArrayIndex = 0;
    let charIndex = 0;
    let isDeleting = false;
    let isEnd = false;
    
    function type() {
        isEnd = false;
        const currentText = texts[textArrayIndex];
        
        if (!isDeleting && charIndex < currentText.length) {
            typedTextSpan.textContent = currentText.substring(0, charIndex + 1);
            charIndex++;
            if (charIndex % 3 === 0) {
                playTypingSound();
            }
        } else if (isDeleting && charIndex > 0) {
            typedTextSpan.textContent = currentText.substring(0, charIndex - 1);
            charIndex--;
        } else if (charIndex === 0) {
            isDeleting = false;
            textArrayIndex++;
            if (textArrayIndex >= texts.length) textArrayIndex = 0;
        } else if (charIndex === currentText.length) {
            isEnd = true;
            isDeleting = true;
        }
        
        const humanizeDelay = Math.random() * 100 + 50;
        const delta = isEnd ? 2000 : isDeleting ? 100 : humanizeDelay;
        
        setTimeout(type, delta);
    }
    
    // Включаем звук по клику
    document.addEventListener("click", function() {
        console.log("Клик зарегистрирован, включаем звук");
        soundEnabled = true;
    }, { once: true });
    
    // Запускаем анимацию сразу после загрузки страницы
    type();
});