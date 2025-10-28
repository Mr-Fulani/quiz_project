document.addEventListener('DOMContentLoaded', function () {
    console.log('Resume enhancement script loaded');

    // Проверка загрузки html2pdf
    if (typeof html2pdf === 'undefined') {
        console.error('html2pdf.js not loaded!');
        alert('Ошибка: библиотека html2pdf не загрузилась. Проверьте подключение.');
        return;
    }
    console.log('html2pdf.js loaded successfully');

    // Переключение языков
    const langButtons = document.querySelectorAll('.lang-btn');
    let currentLang = 'en';

    function setLanguage(lang) {
        currentLang = lang;
        document.querySelectorAll('.lang-text').forEach(el => {
            const langAttr = el.getAttribute('data-lang');
            if (langAttr) {
                el.style.display = langAttr === lang ? 'block' : 'none';
            } else {
                const key = el.getAttribute('data-lang-key');
                if (key === 'education_title') el.textContent = lang === 'en' ? 'Education' : 'Образование';
                if (key === 'experience_title') el.textContent = lang === 'en' ? 'Work History' : 'Опыт работы';
                if (key === 'contact_title') el.textContent = lang === 'en' ? 'Contact Information' : 'Контактная информация';
                if (key === 'personal_info.name') el.textContent = document.getElementById('edit-name') ? document.getElementById('edit-name').value : 'Anvar Sharipov';
            }
        });
    }

    langButtons.forEach(btn => {
        btn.addEventListener('click', function () {
            langButtons.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            setLanguage(this.getAttribute('data-lang'));
        });
    });

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

    // Скачивание PDF
    const downloadBtn = document.getElementById('download-pdf');
    if (downloadBtn) {
        downloadBtn.addEventListener('click', function () {
            console.log('Download PDF button clicked');
            
            // Клонируем весь контейнер резюме
            const originalResume = document.querySelector('article.resume');
            if (!originalResume) {
                console.error('Resume article not found');
                alert('Ошибка: не найден контейнер резюме');
                return;
            }
            
            const resumeElement = originalResume.cloneNode(true);
            
            // Удаляем ненужные элементы
            const elementsToRemove = resumeElement.querySelectorAll('.resume-actions, .language-switcher');
            elementsToRemove.forEach(el => el.remove());
            
            // Показываем только текущий язык
            resumeElement.querySelectorAll('.lang-text').forEach(el => {
                const lang = el.getAttribute('data-lang');
                if (lang && lang !== currentLang) {
                    el.remove();
                } else {
                    el.style.display = 'block';
                }
            });
            
            // Убираем прогресс-бары и декоративные элементы
            const progressBars = resumeElement.querySelectorAll('.skills-progress-bg, .skills-progress-fill, .progress-bar');
            progressBars.forEach(bar => bar.remove());
            
            // Применяем стили для печати
            resumeElement.style.background = '#fff';
            resumeElement.style.color = '#000';
            resumeElement.style.padding = '40px';
            resumeElement.style.boxShadow = 'none';
            resumeElement.style.border = 'none';
            resumeElement.style.borderRadius = '0';
            resumeElement.style.maxWidth = '900px';
            resumeElement.style.margin = '0 auto';
            
            // Меняем цвета текста на темные
            resumeElement.querySelectorAll('h1, h2, h3, h4, .h2, .h3, .h4').forEach(el => {
                el.style.color = '#000';
            });
            
            resumeElement.querySelectorAll('p, li, span, a').forEach(el => {
                el.style.color = '#333';
            });
            
            resumeElement.querySelectorAll('a').forEach(el => {
                el.style.color = '#0066cc';
                el.style.textDecoration = 'underline';
            });
            
            // Создаем контейнер для PDF
            const printContainer = document.createElement('div');
            printContainer.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                width: 210mm;
                min-height: 100vh;
                background: #ffffff;
                padding: 15mm;
                box-sizing: border-box;
                z-index: 9999;
                visibility: hidden;
            `;
            printContainer.appendChild(resumeElement);
            document.body.appendChild(printContainer);

            // Ждем немного чтобы стили применились
            setTimeout(() => {
                printContainer.style.visibility = 'visible';
                
                const options = {
                    margin: [10, 10, 10, 10],
                    filename: `Resume_${currentLang.toUpperCase()}.pdf`,
                    image: { type: 'jpeg', quality: 0.98 },
                    html2canvas: { 
                        scale: 2,
                        useCORS: true,
                        logging: true,
                        backgroundColor: '#ffffff',
                        letterRendering: true,
                        windowWidth: 794,  // A4 width in pixels at 96 DPI
                        windowHeight: 1123 // A4 height in pixels at 96 DPI
                    },
                    jsPDF: { 
                        unit: 'mm',
                        format: 'a4',
                        orientation: 'portrait'
                    }
                };

                console.log('Starting PDF generation...');
                console.log('Container dimensions:', printContainer.offsetWidth, printContainer.offsetHeight);
                
                html2pdf().set(options).from(printContainer).save().then(() => {
                    document.body.removeChild(printContainer);
                    console.log('PDF saved and temporary element removed');
                }).catch(error => {
                    console.error('PDF generation failed:', error);
                    if (printContainer.parentNode) {
                        document.body.removeChild(printContainer);
                    }
                    alert('Ошибка при создании PDF: ' + error.message);
                });
            }, 100);
        });
    } else {
        console.warn('Download PDF button not found');
    }

    // Печать резюме
    const printBtn = document.getElementById('print-resume');
    if (printBtn) {
        printBtn.addEventListener('click', function () {
            console.log('Print button clicked');
            
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