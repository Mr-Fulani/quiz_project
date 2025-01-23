// static/js/typewriter.js

document.addEventListener("DOMContentLoaded", function() {
    const typedTextSpan = document.getElementById("typed-text");
    const cursorSpan = document.getElementById("cursor");
    const typingSound = document.getElementById("typing-sound");

    const texts = ["Выбери тему", "Треннеруйся", "Повышай уровень"]; // Массив текстов для печати
    const typingDelay = 100; // Задержка между символами (мс)
    const erasingDelay = 50; // Задержка между удалением символов (мс)
    const newTextDelay = 2000; // Задержка перед началом печати следующего текста (мс)
    let textIndex = 0;
    let charIndex = 0;

    function type() {
        if (charIndex < texts[textIndex].length) {
            typedTextSpan.textContent += texts[textIndex].charAt(charIndex);
            // Воспроизвести звук, если символ не пробел
            if (texts[textIndex].charAt(charIndex) !== " ") {
                typingSound.currentTime = 0; // Сбросить время воспроизведения
                typingSound.play().catch(error => {
                    console.error("Ошибка воспроизведения звука:", error);
                });
            }
            charIndex++;
            setTimeout(type, typingDelay);
        } else {
            setTimeout(erase, newTextDelay);
        }
    }

    function erase() {
        if (charIndex > 0) {
            typedTextSpan.textContent = texts[textIndex].substring(0, charIndex - 1);
            charIndex--;
            setTimeout(erase, erasingDelay);
        } else {
            textIndex++;
            if (textIndex >= texts.length) textIndex = 0;
            setTimeout(type, typingDelay + 1100);
        }
    }

    // Запуск эффекта печати при клике на кнопку
    const startButton = document.getElementById("start-button");
    if (startButton) {
        startButton.addEventListener("click", function() {
            if (!document.getElementById("typed-text").textContent.length) {
                type();
            }
        });
    } else {
        // Автоматический запуск без кнопки
        setTimeout(type, newTextDelay + 250);
    }
});