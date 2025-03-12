document.addEventListener('DOMContentLoaded', function () {
    console.log('Resume enhancement script loaded');

    // Языковые настройки
    const translations = {
        'en': {
            'education': 'Education',
            'experience': 'Experience',
            'uni1': 'University name',
            'uni1-desc': 'Nemo enims ipsam voluptatem, blanditiis praesentium voluptum delenit atque corrupti, quos dolores et quas molestias exceptur.',
            'uni2': 'University name',
            'uni2-desc': 'Nemo enims ipsam voluptatem, blanditiis praesentium voluptum delenit atque corrupti, quos dolores et quas molestias exceptur.',
            'exp1': 'Company name',
            'exp1-desc': 'Nemo enims ipsam voluptatem, blanditiis praesentium voluptum delenit atque corrupti, quos dolores et quas molestias exceptur.',
            'exp2': 'Company name',
            'exp2-desc': 'Nemo enims ipsam voluptatem, blanditiis praesentium voluptum delenit atque corrupti, quos dolores et quas molestias exceptur.'
        },
        'ru': {
            'education': 'Образование',
            'experience': 'Опыт работы',
            'uni1': 'Название университета',
            'uni1-desc': 'Описание образования на русском языке.',
            'uni2': 'Название университета',
            'uni2-desc': 'Описание образования на русском языке.',
            'exp1': 'Название компании',
            'exp1-desc': 'Описание опыта работы на русском языке.',
            'exp2': 'Название компании',
            'exp2-desc': 'Описание опыта работы на русском языке.'
        },
        'es': {
            'education': 'Educación',
            'experience': 'Experiencia',
            'uni1': 'Nombre de la Universidad',
            'uni1-desc': 'Descripción en español.',
            'uni2': 'Nombre de la Universidad',
            'uni2-desc': 'Descripción en español.',
            'exp1': 'Nombre de la Empresa',
            'exp1-desc': 'Descripción de la experiencia en español.',
            'exp2': 'Nombre de la Empresa',
            'exp2-desc': 'Descripción de la experiencia en español.'
        }
    };

    // Переключение языков
    const langButtons = document.querySelectorAll('.lang-btn');
    if (langButtons.length > 0) {
        langButtons.forEach(btn => {
            btn.addEventListener('click', function () {
                const lang = this.getAttribute('data-lang');
                setLanguage(lang);

                // Активный класс для кнопки
                langButtons.forEach(b => b.classList.remove('active'));
                this.classList.add('active');
            });
        });
    }

    function setLanguage(lang) {
        const elements = document.querySelectorAll('.lang-text');
        elements.forEach(el => {
            const key = el.getAttribute('data-lang-key');
            if (translations[lang] && translations[lang][key]) {
                el.textContent = translations[lang][key];
            }
        });
    }

    // Редактирование резюме
    const editBtn = document.getElementById('edit-resume');
    const editModal = document.getElementById('edit-modal');
    const closeBtn = document.querySelector('.resume-modal .close-btn');
    const cancelBtn = document.querySelector('.resume-modal .cancel-btn');
    const resumeForm = document.getElementById('resume-form');

    // Открытие модального окна
    if (editBtn) {
        editBtn.addEventListener('click', function () {
            // Заполнение формы текущими данными
            populateForm();
            editModal.style.display = 'flex';
        });
    }

    // Закрытие модального окна
    if (closeBtn) {
        closeBtn.addEventListener('click', function () {
            editModal.style.display = 'none';
        });
    }

    if (cancelBtn) {
        cancelBtn.addEventListener('click', function () {
            editModal.style.display = 'none';
        });
    }

    // Закрытие по клику вне модального окна
    window.addEventListener('click', function (e) {
        if (e.target === editModal) {
            editModal.style.display = 'none';
        }
    });

    // Заполнение формы текущими данными
    function populateForm() {
        const title = document.querySelector('.article-title').textContent;
        document.getElementById('edit-title').value = title;

        // Заполнение образования
        const educationItems = document.querySelectorAll('.timeline:nth-of-type(1) .timeline-item');
        const educationContainer = document.getElementById('education-items');
        educationContainer.innerHTML = '';

        educationItems.forEach((item, index) => {
            const title = item.querySelector('.timeline-item-title').textContent;
            const period = item.querySelector('span').textContent;
            const description = item.querySelector('.timeline-text').textContent.trim();

            const html = `
                <div class="education-item" data-index="${index}">
                    <div class="form-group">
                        <label>Institution</label>
                        <input type="text" name="edu-title-${index}" value="${title}">
                    </div>
                    <div class="form-group">
                        <label>Period</label>
                        <input type="text" name="edu-period-${index}" value="${period}">
                    </div>
                    <div class="form-group">
                        <label>Description</label>
                        <textarea name="edu-desc-${index}" rows="3">${description}</textarea>
                    </div>
                    <div class="item-controls">
                        <span class="remove-item" data-type="education" data-index="${index}">
                            <ion-icon name="trash-outline"></ion-icon> Remove
                        </span>
                    </div>
                </div>
            `;
            educationContainer.innerHTML += html;
        });

        // Аналогично для опыта работы
        const experienceItems = document.querySelectorAll('.timeline:nth-of-type(2) .timeline-item');
        const experienceContainer = document.getElementById('experience-items');
        experienceContainer.innerHTML = '';

        experienceItems.forEach((item, index) => {
            const title = item.querySelector('.timeline-item-title').textContent;
            const period = item.querySelector('span').textContent;
            const description = item.querySelector('.timeline-text').textContent.trim();

            const html = `
                <div class="experience-item" data-index="${index}">
                    <div class="form-group">
                        <label>Company</label>
                        <input type="text" name="exp-title-${index}" value="${title}">
                    </div>
                    <div class="form-group">
                        <label>Period</label>
                        <input type="text" name="exp-period-${index}" value="${period}">
                    </div>
                    <div class="form-group">
                        <label>Description</label>
                        <textarea name="exp-desc-${index}" rows="3">${description}</textarea>
                    </div>
                    <div class="item-controls">
                        <span class="remove-item" data-type="experience" data-index="${index}">
                            <ion-icon name="trash-outline"></ion-icon> Remove
                        </span>
                    </div>
                </div>
            `;
            experienceContainer.innerHTML += html;
        });

        // Добавление обработчиков для кнопок удаления
        setupRemoveButtons();
    }

    // Настройка кнопок удаления
    function setupRemoveButtons() {
        const removeButtons = document.querySelectorAll('.remove-item');
        removeButtons.forEach(btn => {
            btn.addEventListener('click', function () {
                const type = this.getAttribute('data-type');
                const index = this.getAttribute('data-index');
                const item = document.querySelector(`.${type}-item[data-index="${index}"]`);
                if (item) {
                    item.remove();
                }
            });
        });
    }

    // Добавление нового образования
    const addEducationBtn = document.getElementById('add-education');
    if (addEducationBtn) {
        addEducationBtn.addEventListener('click', function () {
            const educationContainer = document.getElementById('education-items');
            const index = document.querySelectorAll('.education-item').length;

            const html = `
                <div class="education-item" data-index="${index}">
                    <div class="form-group">
                        <label>Institution</label>
                        <input type="text" name="edu-title-${index}" value="New Institution">
                    </div>
                    <div class="form-group">
                        <label>Period</label>
                        <input type="text" name="edu-period-${index}" value="20XX — 20XX">
                    </div>
                    <div class="form-group">
                        <label>Description</label>
                        <textarea name="edu-desc-${index}" rows="3">Description of your education</textarea>
                    </div>
                    <div class="item-controls">
                        <span class="remove-item" data-type="education" data-index="${index}">
                            <ion-icon name="trash-outline"></ion-icon> Remove
                        </span>
                    </div>
                </div>
            `;
            educationContainer.innerHTML += html;
            setupRemoveButtons();
        });
    }

    // Добавление нового опыта
    const addExperienceBtn = document.getElementById('add-experience');
    if (addExperienceBtn) {
        addExperienceBtn.addEventListener('click', function () {
            const experienceContainer = document.getElementById('experience-items');
            const index = document.querySelectorAll('.experience-item').length;

            const html = `
                <div class="experience-item" data-index="${index}">
                    <div class="form-group">
                        <label>Company</label>
                        <input type="text" name="exp-title-${index}" value="New Company">
                    </div>
                    <div class="form-group">
                        <label>Period</label>
                        <input type="text" name="exp-period-${index}" value="20XX — Present">
                    </div>
                    <div class="form-group">
                        <label>Description</label>
                        <textarea name="exp-desc-${index}" rows="3">Description of your experience</textarea>
                    </div>
                    <div class="item-controls">
                        <span class="remove-item" data-type="experience" data-index="${index}">
                            <ion-icon name="trash-outline"></ion-icon> Remove
                        </span>
                    </div>
                </div>
            `;
            experienceContainer.innerHTML += html;
            setupRemoveButtons();
        });
    }

    // Сохранение изменений
    if (resumeForm) {
        resumeForm.addEventListener('submit', function (e) {
            e.preventDefault();

            // Обновление заголовка
            const title = document.getElementById('edit-title').value;
            document.querySelector('.article-title').textContent = title;

            // Обновление образования
            const educationItems = document.querySelectorAll('.education-item');
            const educationList = document.querySelector('.timeline:nth-of-type(1) .timeline-list');
            educationList.innerHTML = '';

            educationItems.forEach((item, index) => {
                const title = item.querySelector('input[name^="edu-title"]').value;
                const period = item.querySelector('input[name^="edu-period"]').value;
                const description = item.querySelector('textarea[name^="edu-desc"]').value;

                const html = `
                    <li class="timeline-item">
                        <h4 class="h4 timeline-item-title lang-text" data-lang-key="edu-${index}">${title}</h4>
                        <span>${period}</span>
                        <p class="timeline-text lang-text" data-lang-key="edu-${index}-desc">
                            ${description}
                        </p>
                    </li>
                `;
                educationList.innerHTML += html;
            });

            // Обновление опыта работы
            const experienceItems = document.querySelectorAll('.experience-item');
            const experienceList = document.querySelector('.timeline:nth-of-type(2) .timeline-list');
            experienceList.innerHTML = '';

            experienceItems.forEach((item, index) => {
                const title = item.querySelector('input[name^="exp-title"]').value;
                const period = item.querySelector('input[name^="exp-period"]').value;
                const description = item.querySelector('textarea[name^="exp-desc"]').value;

                const html = `
                    <li class="timeline-item">
                        <h4 class="h4 timeline-item-title lang-text" data-lang-key="exp-${index}">${title}</h4>
                        <span>${period}</span>
                        <p class="timeline-text lang-text" data-lang-key="exp-${index}-desc">
                            ${description}
                        </p>
                    </li>
                `;
                experienceList.innerHTML += html;
            });

            // Закрытие модального окна
            editModal.style.display = 'none';

            // Обновление переводов
            const activeLang = document.querySelector('.lang-btn.active').getAttribute('data-lang');
            setLanguage(activeLang);
        });
    }

    // Скачивание PDF
    const downloadPdfBtn = document.getElementById('download-pdf');
    if (downloadPdfBtn) {
        downloadPdfBtn.addEventListener('click', function () {
            const resumeElement = document.querySelector('.resume');
            const options = {
                margin: 10,
                filename: 'resume.pdf',
                image: {type: 'jpeg', quality: 0.98},
                html2canvas: {scale: 2},
                jsPDF: {unit: 'mm', format: 'a4', orientation: 'portrait'}
            };

            // Временно скрываем кнопки действий для PDF
            const actions = document.querySelector('.resume-actions');
            const actionsDisplay = actions.style.display;
            actions.style.display = 'none';

            html2pdf().from(resumeElement).set(options).save().then(() => {
                // Возвращаем отображение кнопок
                actions.style.display = actionsDisplay;
            });
        });
    }

    // Печать резюме
    const printBtn = document.getElementById('print-resume');
    if (printBtn) {
        printBtn.addEventListener('click', function () {
            window.print();
        });
    }

    // Скачивание DOCX
    const downloadDocxBtn = document.getElementById('download-docx');
    if (downloadDocxBtn) {
        downloadDocxBtn.addEventListener('click', function () {
            // Используем более простой подход - создаем текстовый документ
            try {
                // Проверяем наличие библиотеки
                if (typeof docx === 'undefined') {
                    throw new Error("DOCX library not loaded");
                }

                // Получаем данные
                const title = document.querySelector('.article-title').textContent.trim();

                // Создаем документ
                const doc = new docx.Document();

                // Добавляем заголовок
                const children = [
                    new docx.Paragraph({
                        children: [
                            new docx.TextRun({
                                text: title,
                                bold: true,
                                size: 36
                            })
                        ],
                        alignment: docx.AlignmentType.CENTER,
                        spacing: {after: 400}
                    })
                ];

                // Добавляем образование
                children.push(
                    new docx.Paragraph({
                        children: [
                            new docx.TextRun({
                                text: document.querySelector('.timeline:nth-of-type(1) .h3').textContent.trim(),
                                bold: true,
                                size: 28
                            })
                        ],
                        spacing: {before: 400, after: 200}
                    })
                );

                // Добавляем элементы образования
                document.querySelectorAll('.timeline:nth-of-type(1) .timeline-item').forEach(item => {
                    const title = item.querySelector('.timeline-item-title').textContent.trim();
                    const period = item.querySelector('span').textContent.trim();
                    const desc = item.querySelector('.timeline-text').textContent.trim();

                    children.push(
                        new docx.Paragraph({
                            children: [
                                new docx.TextRun({
                                    text: title,
                                    bold: true,
                                    size: 24
                                })
                            ],
                            spacing: {before: 200}
                        }),
                        new docx.Paragraph({
                            children: [
                                new docx.TextRun({
                                    text: period,
                                    italics: true
                                })
                            ],
                            spacing: {before: 100}
                        }),
                        new docx.Paragraph({
                            children: [
                                new docx.TextRun({
                                    text: desc
                                })
                            ],
                            spacing: {before: 100, after: 200}
                        })
                    );
                });

                // Добавляем опыт работы
                children.push(
                    new docx.Paragraph({
                        children: [
                            new docx.TextRun({
                                text: document.querySelector('.timeline:nth-of-type(2) .h3').textContent.trim(),
                                bold: true,
                                size: 28
                            })
                        ],
                        spacing: {before: 400, after: 200}
                    })
                );

                // Добавляем элементы опыта
                document.querySelectorAll('.timeline:nth-of-type(2) .timeline-item').forEach(item => {
                    const title = item.querySelector('.timeline-item-title').textContent.trim();
                    const period = item.querySelector('span').textContent.trim();
                    const desc = item.querySelector('.timeline-text').textContent.trim();

                    children.push(
                        new docx.Paragraph({
                            children: [
                                new docx.TextRun({
                                    text: title,
                                    bold: true,
                                    size: 24
                                })
                            ],
                            spacing: {before: 200}
                        }),
                        new docx.Paragraph({
                            children: [
                                new docx.TextRun({
                                    text: period,
                                    italics: true
                                })
                            ],
                            spacing: {before: 100}
                        }),
                        new docx.Paragraph({
                            children: [
                                new docx.TextRun({
                                    text: desc
                                })
                            ],
                            spacing: {before: 100, after: 200}
                        })
                    );
                });

                // Добавляем секцию с параграфами
                doc.addSection({children});

                // Сохраняем документ
                docx.Packer.toBlob(doc).then(blob => {
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = 'resume.docx';
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    document.body.removeChild(a);
                });

            } catch (error) {
                console.error("Error creating DOCX:", error);

                // Если библиотека не загружена, предложим альтернативу
                if (confirm("DOCX generation failed. Would you like to download as a text file instead?")) {
                    // Создаем текстовый файл как запасной вариант
                    const title = document.querySelector('.article-title').textContent;
                    let content = title + "\n\n";

                    // Добавляем образование
                    content += document.querySelector('.timeline:nth-of-type(1) .h3').textContent + "\n";
                    document.querySelectorAll('.timeline:nth-of-type(1) .timeline-item').forEach(item => {
                        content += "- " + item.querySelector('.timeline-item-title').textContent + "\n";
                        content += "  " + item.querySelector('span').textContent + "\n";
                        content += "  " + item.querySelector('.timeline-text').textContent.trim() + "\n\n";
                    });

                    // Добавляем опыт
                    content += document.querySelector('.timeline:nth-of-type(2) .h3').textContent + "\n";
                    document.querySelectorAll('.timeline:nth-of-type(2) .timeline-item').forEach(item => {
                        content += "- " + item.querySelector('.timeline-item-title').textContent + "\n";
                        content += "  " + item.querySelector('span').textContent + "\n";
                        content += "  " + item.querySelector('.timeline-text').textContent.trim() + "\n\n";
                    });

                    // Создаем и скачиваем текстовый файл
                    const blob = new Blob([content], {type: 'text/plain'});
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = 'resume.txt';
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    document.body.removeChild(a);
                }
            }
        });
    }
});