document.addEventListener('DOMContentLoaded', function() {
    const metaDescriptionField = document.querySelector('#id_meta_description');
    const maxLength = 160;

    if (metaDescriptionField) {
        // Создаём элемент для отображения предупреждения
        const warning = document.createElement('p');
        warning.style.color = 'red';
        warning.style.marginTop = '5px';
        metaDescriptionField.parentNode.appendChild(warning);

        // Функция проверки длины
        function checkLength() {
            const length = metaDescriptionField.value.length;
            if (length > maxLength) {
                warning.textContent = `Мета-описание превышает ${maxLength} символов (текущая длина: ${length}).`;
                metaDescriptionField.style.borderColor = 'red';
            } else {
                warning.textContent = `Длина: ${length}/${maxLength}`;
                warning.style.color = length > 140 ? 'orange' : 'green';
                metaDescriptionField.style.borderColor = '';
            }
        }

        // Проверка при вводе
        metaDescriptionField.addEventListener('input', checkLength);
        // Проверка при загрузке страницы
        checkLength();
    }
});