// // Массив цветов для фона
// const colors = ["#ffeb3b", "#fdd835", "#ffc107", "#ff9800", "#ff5722", "#8bc34a", "#00bcd4", "#673ab7"];
// let currentColorIndex = 0;
//
// // Функция смены цвета
// function changeBackgroundColor() {
//     console.log("Кнопка нажата"); // Лог для проверки
//     currentColorIndex = (currentColorIndex + 1) % colors.length;
//     document.body.style.backgroundColor = colors[currentColorIndex];
// }
//
// // Привязываем событие клика к кнопке
// document.addEventListener("DOMContentLoaded", () => {
//     const button = document.getElementById("register");
//     if (button) {
//         console.log("Кнопка найдена, привязываем обработчик");
//         button.addEventListener("click", changeBackgroundColor);
//     } else {
//         console.error("Кнопка не найдена!");
//     }
// });

document.addEventListener("DOMContentLoaded", () => {
    const messageElement = document.getElementById("message");

    fetch("https://4664-185-241-101-16.ngrok-free.app/api/test-api/")
        .then((response) => {
            if (!response.ok) {
                throw new Error("Network response was not ok");
            }
            return response.json();
        })
        .then((data) => {
            messageElement.textContent = data.message; // Отображаем данные
        })
        .catch((error) => {
            console.error("Ошибка при загрузке данных:", error);
            messageElement.textContent = "Не удалось загрузить данные.";
        });
});