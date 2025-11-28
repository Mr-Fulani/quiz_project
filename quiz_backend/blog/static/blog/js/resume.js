document.addEventListener('DOMContentLoaded', function () {
    console.log('Resume enhancement script loaded');

    // Переключение языков - только для резюме (инициализируем независимо от html2pdf)
    const resumeContainer = document.getElementById('resume-content');
    if (!resumeContainer) {
        console.warn('Resume container not found');
        return;
    }
    
    const langButtons = resumeContainer.querySelectorAll('.language-switcher .lang-btn');
    let currentLang = 'en';

    function setLanguage(lang) {
        console.log('Setting resume language to:', lang);
        currentLang = lang;
        
        // Словарь переводов заголовков
        const translations = {
            'resume_title': { 'en': 'Resume', 'ru': 'Резюме' },
            'education_title': { 'en': 'Education', 'ru': 'Образование' },
            'experience_title': { 'en': 'Work History', 'ru': 'Опыт Работы' },
            'contact_title': { 'en': 'Contact Information', 'ru': 'Контактная Информация' },
            'summary_title': { 'en': 'Professional Summary', 'ru': 'Профессиональная Сводка' },
            'skills_title': { 'en': 'Skills', 'ru': 'Навыки' },
            'languages_title': { 'en': 'Languages', 'ru': 'Языки' }
        };
        
        // Находим все элементы с переводами только внутри резюме
        const langTextElements = resumeContainer.querySelectorAll('.lang-text');
        console.log('Found', langTextElements.length, 'elements with lang-text class');
        
        langTextElements.forEach(el => {
            const langAttr = el.getAttribute('data-lang');
            const langKey = el.getAttribute('data-lang-key');
            
            // Если есть data-lang, показываем/скрываем элемент
            if (langAttr) {
                el.style.display = langAttr === lang ? 'block' : 'none';
            }
            
            // Если есть data-lang-key, меняем текст заголовка
            if (langKey && translations[langKey]) {
                const translation = translations[langKey][lang];
                if (translation) {
                    console.log(`Translating "${langKey}" to "${translation}"`);
                    el.textContent = translation;
                }
            } else if (langKey === 'personal_info.name') {
                // Специальная обработка для имени
                el.textContent = document.getElementById('edit-name') ? document.getElementById('edit-name').value : 'Anvar Sharipov';
            }
        });
        console.log('Language switched to:', lang);
    }

    if (langButtons.length > 0) {
        console.log('Found', langButtons.length, 'language buttons in resume');
        langButtons.forEach(btn => {
            btn.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();
                const targetLang = this.getAttribute('data-lang');
                console.log('Language button clicked:', targetLang);
                
                // Обновляем активную кнопку только в переключателе резюме
                resumeContainer.querySelectorAll('.language-switcher .lang-btn').forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                
                setLanguage(targetLang);
            });
        });
    } else {
        console.warn('Language buttons not found in resume');
    }

    setLanguage('en');

    // Редактирование
    const editBtn = document.getElementById('edit-resume');
    const editModal = document.getElementById('edit-modal');
    const closeBtn = document.querySelector('.resume-modal .close-btn');
    const cancelBtn = document.querySelector('.resume-modal .cancel-btn');
    const resumeForm = document.getElementById('resume-form');

    if (editBtn) {
        editBtn.addEventListener('click', function () {
            console.log('Edit button clicked');
            editModal.style.display = 'flex';
        });
    } else {
        console.warn('Edit button not found');
    }

    if (closeBtn) closeBtn.addEventListener('click', () => editModal.style.display = 'none');
    if (cancelBtn) cancelBtn.addEventListener('click', () => editModal.style.display = 'none');
    window.addEventListener('click', e => { if (e.target === editModal) editModal.style.display = 'none'; });

    if (resumeForm) {
        resumeForm.addEventListener('submit', function (e) {
            e.preventDefault();
            console.log('Form submitted');
            
            // Собираем данные для отправки на сервер
            const websites = document.getElementById('edit-websites').value.split(',').map(w => w.trim()).filter(w => w);
            const skills = document.getElementById('edit-skills').value.split(',').map(s => s.trim()).filter(s => s);
            const respEn = document.getElementById('edit-job1-responsibilities-en').value.split(';').map(r => r.trim()).filter(r => r);
            const respRu = document.getElementById('edit-job1-responsibilities-ru').value.split(';').map(r => r.trim()).filter(r => r);
            
            const formData = {
                name: document.getElementById('edit-name').value,
                contact_info_en: document.getElementById('edit-contact-en').value,
                contact_info_ru: document.getElementById('edit-contact-ru').value,
                email: document.getElementById('edit-email').value,
                websites: websites,
                summary_en: document.getElementById('edit-summary-en').value,
                summary_ru: document.getElementById('edit-summary-ru').value,
                skills: skills,
                work_history: [{
                    title_en: document.getElementById('edit-job1-title-en').value,
                    title_ru: document.getElementById('edit-job1-title-ru').value,
                    period_en: document.getElementById('edit-job1-period-en').value,
                    period_ru: document.getElementById('edit-job1-period-ru').value,
                    company_en: document.getElementById('edit-job1-company-en').value,
                    company_ru: document.getElementById('edit-job1-company-ru').value,
                    responsibilities_en: respEn,
                    responsibilities_ru: respRu
                }]
            };
            
            // Получаем CSRF токен
            const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || 
                              document.querySelector('meta[name="csrf-token"]')?.content ||
                              getCookie('csrftoken');
            
            // Отправляем данные на сервер
            fetch('/api/resume/save/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrftoken
                },
                body: JSON.stringify(formData)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    console.log('Резюме успешно сохранено:', data);
                    
                    // Обновляем DOM после успешного сохранения
                    document.querySelector('.h2.article-title[data-lang-key="personal_info.name"]').textContent = formData.name;
                    document.querySelector('.contact-info .location-phone.lang-text[data-lang="en"]').textContent = formData.contact_info_en;
                    document.querySelector('.contact-info .location-phone.lang-text[data-lang="ru"]').textContent = formData.contact_info_ru;
                    document.querySelector('.contact-info .email').innerHTML = `<a href="mailto:${formData.email}">${formData.email}</a>`;
                    if (websites[0]) document.querySelector('.contact-info p:nth-child(3)').innerHTML = `<a href="${websites[0]}" target="_blank">${websites[0]}</a>`;
                    if (websites[1]) document.querySelector('.contact-info p:nth-child(4)').innerHTML = `<a href="${websites[1]}" target="_blank">${websites[1]}</a>`;
                    document.querySelector('.timeline-text.lang-text[data-lang="en"]').textContent = formData.summary_en;
                    document.querySelector('.timeline-text.lang-text[data-lang="ru"]').textContent = formData.summary_ru;
            document.querySelector('.skills-list').innerHTML = skills.map(s => `<li>${s}</li>`).join('');
                    document.querySelector('.timeline-list li:nth-child(1) .h4.lang-text[data-lang="en"]').textContent = formData.work_history[0].title_en;
                    document.querySelector('.timeline-list li:nth-child(1) .h4.lang-text[data-lang="ru"]').textContent = formData.work_history[0].title_ru;
                    document.querySelector('.timeline-list li:nth-child(1) span.lang-text[data-lang="en"]').textContent = formData.work_history[0].period_en;
                    document.querySelector('.timeline-list li:nth-child(1) span.lang-text[data-lang="ru"]').textContent = formData.work_history[0].period_ru;
                    document.querySelector('.timeline-list li:nth-child(1) p.lang-text[data-lang="en"]').textContent = formData.work_history[0].company_en;
                    document.querySelector('.timeline-list li:nth-child(1) p.lang-text[data-lang="ru"]').textContent = formData.work_history[0].company_ru;
                    document.querySelector('.timeline-list li:nth-child(1) .responsibilities').innerHTML = respEn.map((r, i) => 
                        `<li class="lang-text" data-lang="en">${r}</li><li class="lang-text" data-lang="ru">${respRu[i] || ''}</li>`
                    ).join('');

            editModal.style.display = 'none';
            setLanguage(currentLang);
                    
                    alert('Резюме успешно сохранено!');
                } else {
                    console.error('Ошибка сохранения:', data);
                    alert('Ошибка при сохранении резюме: ' + (data.error || 'Неизвестная ошибка'));
                }
            })
            .catch(error => {
                console.error('Ошибка при отправке:', error);
                alert('Ошибка при сохранении резюме. Проверьте консоль для деталей.');
            });
        });
    }
    
    // Функция для получения CSRF токена из cookies
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

    // Скачивание PDF - серверная генерация (надёжно!)
    const downloadBtn = document.getElementById('download-pdf');
    console.log('Download PDF button found:', downloadBtn);
    if (downloadBtn) {
        downloadBtn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            console.log('Download PDF - server-side generation');
            
            // Просто редиректим на серверный endpoint (URL берём из шаблона с учётом i18n-префикса)
            const downloadUrlBase = downloadBtn.getAttribute('data-download-url') || '/resume/download/';
            window.location.href = `${downloadUrlBase}?lang=${currentLang}`;
        });
    } else {
        console.warn('Download PDF button not found');
    }
    
    // Проверка загрузки html2pdf (не критична для основной функциональности)
    if (typeof html2pdf === 'undefined') {
        console.warn('html2pdf.js not loaded - PDF download via client-side will not work');
    } else {
        console.log('html2pdf.js loaded successfully');
    }

    // Печать резюме
    const printBtn = document.getElementById('print-resume');
    console.log('Print button found:', printBtn);
    if (printBtn) {
        printBtn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            console.log('Print button clicked - opening print dialog');
            
            // Временно скрываем элементы, которые не нужны при печати
            const hideElements = document.querySelectorAll('.resume-actions, .language-switcher');
            hideElements.forEach(el => el.style.display = 'none');
            
            // Показываем только текущий язык
            document.querySelectorAll('.lang-text').forEach(el => {
                const lang = el.getAttribute('data-lang');
                if (lang && lang !== currentLang) {
                    el.style.display = 'none';
                }
            });
            
            // Печатаем
        window.print();
            
            // Возвращаем элементы обратно
            setTimeout(() => {
                hideElements.forEach(el => el.style.display = '');
                setLanguage(currentLang); // Восстанавливаем отображение языков
            }, 100);
        });
    }
});