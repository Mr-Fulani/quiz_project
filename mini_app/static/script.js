// Выполняется, когда документ (DOM) загружен
document.addEventListener("DOMContentLoaded", function() {
  // Находим элементы по их ID
  const launchBtn = document.getElementById("launch-btn");
  const closeBtn = document.getElementById("close-btn");
  const modalOverlay = document.getElementById("modal-overlay");
  const appMenu = document.getElementById("app-menu");


  // Обработчик кнопки "Запустить приложение"
  launchBtn.addEventListener("click", function() {
    // Скрываем модальное окно
    modalOverlay.style.display = "none";
    // Показываем основной контент приложения
    appMenu.style.display = "block";

    // Если нужно — отправляем какие-то данные боту
    if (window.Telegram && window.Telegram.WebApp) {
      window.Telegram.WebApp.sendData(JSON.stringify({ action: "launch" }));
    }
  });
});

// Пример обработчика для кнопок меню
function handleMenu(action) {
  alert("Вы нажали: " + action);
  // Если требуется — передаём данные боту
  if (window.Telegram && window.Telegram.WebApp) {
    window.Telegram.WebApp.sendData(JSON.stringify({ action: action }));
  }
}