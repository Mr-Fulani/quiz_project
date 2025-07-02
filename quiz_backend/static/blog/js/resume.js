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
            // Name
            document.querySelector('.h2.article-title').textContent = document.getElementById('edit-name').value;
            // Contact Info
            document.querySelector('.contact-info .location-phone.lang-text[data-lang="en"]').textContent = document.getElementById('edit-contact-en').value;
            document.querySelector('.contact-info .location-phone.lang-text[data-lang="ru"]').textContent = document.getElementById('edit-contact-ru').value;
            document.querySelector('.contact-info .email').innerHTML = `<a href="mailto:${document.getElementById('edit-email').value}">${document.getElementById('edit-email').value}</a>`;
            const websites = document.getElementById('edit-websites').value.split(',').map(w => w.trim());
            document.querySelector('.contact-info p:nth-child(3)').innerHTML = `<a href="${websites[0]}" target="_blank">${websites[0]}</a>`;
            document.querySelector('.contact-info p:nth-child(4)').innerHTML = `<a href="${websites[1]}" target="_blank">${websites[1]}</a>`;
            // Summary
            document.querySelector('.timeline-text.lang-text[data-lang="en"]').textContent = document.getElementById('edit-summary-en').value;
            document.querySelector('.timeline-text.lang-text[data-lang="ru"]').textContent = document.getElementById('edit-summary-ru').value;
            // Skills
            const skills = document.getElementById('edit-skills').value.split(',').map(s => s.trim());
            document.querySelector('.skills-list').innerHTML = skills.map(s => `<li>${s}</li>`).join('');
            // Work History (пример для первой записи)
            document.querySelector('.timeline-list li:nth-child(1) .h4.lang-text[data-lang="en"]').textContent = document.getElementById('edit-job1-title-en').value;
            document.querySelector('.timeline-list li:nth-child(1) .h4.lang-text[data-lang="ru"]').textContent = document.getElementById('edit-job1-title-ru').value;
            document.querySelector('.timeline-list li:nth-child(1) span.lang-text[data-lang="en"]').textContent = document.getElementById('edit-job1-period-en').value;
            document.querySelector('.timeline-list li:nth-child(1) span.lang-text[data-lang="ru"]').textContent = document.getElementById('edit-job1-period-ru').value;
            document.querySelector('.timeline-list li:nth-child(1) p.lang-text[data-lang="en"]').textContent = document.getElementById('edit-job1-company-en').value;
            document.querySelector('.timeline-list li:nth-child(1) p.lang-text[data-lang="ru"]').textContent = document.getElementById('edit-job1-company-ru').value;
            const respEn = document.getElementById('edit-job1-responsibilities-en').value.split(';').map(r => r.trim());
            const respRu = document.getElementById('edit-job1-responsibilities-ru').value.split(';').map(r => r.trim());
            document.querySelector('.timeline-list li:nth-child(1) .responsibilities').innerHTML = respEn.map((r, i) => `<li class="lang-text" data-lang="en">${r}</li><li class="lang-text" data-lang="ru">${respRu[i]}</li>`).join('');

            editModal.style.display = 'none';
            setLanguage(currentLang);
        });
    }

    // Скачивание PDF
    const downloadBtn = document.getElementById('download-pdf');
    if (downloadBtn) {
        downloadBtn.addEventListener('click', function () {
            console.log('Download PDF button clicked');
            const resumeElement = document.getElementById('resume-content').cloneNode(true);
            resumeElement.querySelector('.resume-actions').style.display = 'none';
            resumeElement.querySelector('.language-switcher').style.display = 'none';
            resumeElement.querySelectorAll('.lang-text').forEach(el => {
                if (el.getAttribute('data-lang') !== currentLang) el.style.display = 'none';
                else el.style.display = 'block';
            });
            resumeElement.querySelectorAll('.progress-bar').forEach(bar => {
                bar.style.display = 'none'; // Убираем прогресс-бары
            });

            const printContainer = document.createElement('div');
            printContainer.style.position = 'absolute';
            printContainer.style.top = '0';
            printContainer.style.left = '-9999px';
            printContainer.style.width = '900px';
            printContainer.style.padding = '20px';
            printContainer.appendChild(resumeElement);
            document.body.appendChild(printContainer);

            const options = {
                margin: 0.5,
                filename: `Anvar_Sharipov_Resume_${currentLang}.pdf`,
                image: { type: 'jpeg', quality: 0.98 },
                html2canvas: { scale: 2, useCORS: true, logging: true },
                jsPDF: { unit: 'in', format: 'letter', orientation: 'portrait' }
            };

            console.log('Starting PDF generation...');
            html2pdf().set(options).from(printContainer).toPdf().get('pdf').then(pdf => {
                pdf.setFont('times');
                pdf.setFontSize(11);
                console.log('PDF generated successfully');
            }).save().then(() => {
                document.body.removeChild(printContainer);
                console.log('PDF saved and temporary element removed');
            }).catch(error => {
                console.error('PDF generation failed:', error);
                document.body.removeChild(printContainer);
                alert('Ошибка при создании PDF: ' + error.message);
            });
        });
    } else {
        console.warn('Download PDF button not found');
    }

    document.getElementById('print-resume').addEventListener('click', function () {
        console.log('Print button clicked');
        window.print();
    });
});