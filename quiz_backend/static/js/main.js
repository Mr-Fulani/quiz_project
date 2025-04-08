'use strict';

console.log("main.js loaded");

document.addEventListener('DOMContentLoaded', function () {
    const elementToggleFunc = function (elem) {
        elem.classList.toggle("active");
    }

    const sidebar = document.querySelector("[data-sidebar]");
    const sidebarBtn = document.querySelector("[data-sidebar-btn]");
    if (sidebarBtn) sidebarBtn.addEventListener("click", function () {
        elementToggleFunc(sidebar);
    });

    const testimonialsItem = document.querySelectorAll('[data-testimonials-item]');
    const modalContainer = document.querySelector('[data-modal-container]');
    const modalCloseBtn = document.querySelector('[data-modal-close-btn]');
    const overlay = document.querySelector('[data-overlay]');
    const modalImg = document.querySelector('[data-modal-img]');
    const modalTitle = document.querySelector('[data-modal-title]');
    const modalText = document.querySelector('[data-modal-text]');
    const modalDate = document.querySelector('[data-modal-date]');
    const modalProfileLink = document.querySelector('[data-profile-link]');

    console.log("Found testimonials items:", testimonialsItem.length);

    const testimonialsModalFunc = function () {
        if (modalContainer && overlay) {
            modalContainer.classList.toggle('active');
            overlay.classList.toggle('active');
            console.log("Modal toggled, active:", modalContainer.classList.contains('active'));
        } else {
            console.error("Modal container or overlay not found");
        }
    }

    for (let i = 0; i < testimonialsItem.length; i++) {
        testimonialsItem[i].addEventListener('click', function () {
            console.log("Card clicked:", i);
            const avatar = this.querySelector('[data-testimonials-avatar]').src;
            const alt = this.querySelector('[data-testimonials-avatar]').alt;
            const title = this.querySelector('[data-testimonials-title]').textContent;
            const text = this.querySelector('[data-testimonials-text]').innerHTML;
            const date = this.querySelector('[data-date-joined]') ? this.querySelector('[data-date-joined]').textContent : "14 June, 2023";
            const username = this.parentElement.getAttribute('data-username');

            console.log("Avatar:", avatar);
            console.log("Title:", title);
            console.log("Text:", text);
            console.log("Date:", date);
            console.log("Username:", username);

            if (modalImg) modalImg.src = avatar; else console.error("modalImg not found");
            if (modalImg) modalImg.alt = alt;
            if (modalTitle) modalTitle.textContent = title; else console.error("modalTitle not found");
            if (modalText) modalText.innerHTML = text; else console.error("modalText not found");
            if (modalDate) modalDate.textContent = "Member since: " + date; else console.error("modalDate not found");

            if (modalProfileLink && username) {
                // Исправлено: правильный путь к профилю
                modalProfileLink.href = `/users/user/${encodeURIComponent(username)}/`;
                modalProfileLink.dataset.username = username;
                console.log("Profile link set to:", modalProfileLink.href);
                console.log("data-username set to:", modalProfileLink.dataset.username);
            } else if (!modalProfileLink) {
                console.error("modalProfileLink not found");
            } else if (!username) {
                console.error("Username not found in data-username attribute");
            }

            testimonialsModalFunc();
        });
    }

    if (modalCloseBtn) modalCloseBtn.addEventListener('click', testimonialsModalFunc);
    if (overlay) overlay.addEventListener('click', testimonialsModalFunc);

    /**
     * Логика модального окна для видео.
     * Отображает видео из YouTube или локального источника.
     */
    const videoItems = document.querySelectorAll('[data-video-item]');
    const videoModalContainer = document.querySelector('[data-video-modal-container]');
    const videoCloseBtn = document.querySelector('[data-video-close-btn]');
    const videoOverlay = document.querySelector('[data-video-overlay]');
    const videoPlayer = document.querySelector('[data-video-player]');

    /**
     * Функция переключения видимости модального окна видео и очистки плеера при закрытии.
     */
    const videoModalFunc = function () {
        videoModalContainer.classList.toggle('active');
        videoOverlay.classList.toggle('active');
        if (!videoModalContainer.classList.contains('active')) {
            if (videoPlayer) videoPlayer.innerHTML = '';
        }
    }

    for (let i = 0; i < videoItems.length; i++) {
        videoItems[i].addEventListener('click', function () {
            const isYouTube = this.querySelector('.video-banner-box img')?.src.includes('youtube');
            let videoUrl;

            if (isYouTube) {
                const videoIdMatch = this.querySelector('.video-banner-box img').src.match(/vi\/(.+?)\/hqdefault/);
                const videoId = videoIdMatch ? videoIdMatch[1] : '';
                videoUrl = `https://www.youtube.com/embed/${videoId}?enablejsapi=1&autoplay=1`;
            } else {
                videoUrl = this.querySelector('.video-banner-box video source')?.src;
            }

            if (videoUrl) {
                if (isYouTube) {
                    videoPlayer.innerHTML = `<iframe width="100%" height="400" src="${videoUrl}" frameborder="0" allowfullscreen></iframe>`;
                } else {
                    videoPlayer.innerHTML = `<video width="100%" height="400" controls><source src="${videoUrl}" type="video/mp4"></video>`;
                }
                videoModalFunc();
            } else {
                console.error("Video URL not found for item:", this);
            }
        });
    }

    if (videoCloseBtn) videoCloseBtn.addEventListener('click', videoModalFunc);
    if (videoOverlay) videoOverlay.addEventListener('click', videoModalFunc);

    /**
     * Логика фильтрации элементов через селект и кнопки.
     */
    const select = document.querySelector('[data-select]');
    const selectItems = document.querySelectorAll('[data-select-item]');
    const selectValue = document.querySelector('[data-select-value]');
    const filterBtn = document.querySelectorAll('[data-filter-btn]');

    if (select) select.addEventListener('click', function () {
        elementToggleFunc(this);
    });

    for (let i = 0; i < selectItems.length; i++) {
        selectItems[i].addEventListener('click', function () {
            let selectedValue = this.innerText.toLowerCase();
            selectValue.innerText = this.innerText;
            elementToggleFunc(select);
            filterFunc(selectedValue);
        });
    }

    const filterItems = document.querySelectorAll('[data-filter-item]');

    /**
     * Функция фильтрации элементов по выбранной категории.
     * @param {string} selectedValue - Значение выбранного фильтра.
     */
    const filterFunc = function (selectedValue) {
        console.log("Filtering with value:", selectedValue);
        for (let i = 0; i < filterItems.length; i++) {
            const category = filterItems[i].dataset.category;
            if (selectedValue === "all") {
                filterItems[i].classList.add('active');
            } else if (selectedValue === category) {
                filterItems[i].classList.add('active');
            } else {
                filterItems[i].classList.remove('active');
            }
        }
    }

    /**
     * Активация кнопок фильтрации для больших экранов.
     */
    console.log("Filter buttons found:", filterBtn.length);
    let lastClickedBtn = filterBtn[0];

    for (let i = 0; i < filterBtn.length; i++) {
        filterBtn[i].addEventListener('click', function () {
            let selectedValue = this.innerText.toLowerCase();
            if (selectValue) selectValue.innerText = this.innerText;
            filterFunc(selectedValue);

            if (lastClickedBtn) lastClickedBtn.classList.remove('active');
            this.classList.add('active');
            lastClickedBtn = this;
        });
    }

    /**
     * Инициализация фильтрации при загрузке страницы.
     */
    if (filterBtn.length > 0) {
        console.log("Initializing filter with first button");
        filterBtn[0].click();
    } else {
        console.error("No filter buttons found. Check .filter-list visibility or [data-filter-btn] elements.");
    }

    /**
     * Активация кнопки отправки формы при валидности данных.
     */
    const form = document.querySelector('[data-form]');
    const formInputs = document.querySelectorAll('[data-form-input]');
    const formBtn = document.querySelector('[data-form-btn]');

    for (let i = 0; i < formInputs.length; i++) {
        formInputs[i].addEventListener('input', function () {
            if (form.checkValidity()) {
                formBtn.removeAttribute('disabled');
            } else {
                formBtn.setAttribute('disabled', '');
            }
        });
    }

    /**
     * Навигация по страницам через ссылки.
     */
    const navigationLinks = document.querySelectorAll('[data-nav-link]');
    const pages = document.querySelectorAll('[data-page]');

    for (let i = 0; i < navigationLinks.length; i++) {
        navigationLinks[i].addEventListener('click', function () {
            for (let j = 0; j < pages.length; j++) {
                if (this.innerHTML.toLowerCase() === pages[j].dataset.page) {
                    pages[j].classList.add('active');
                    navigationLinks[j].classList.add('active');
                    window.scrollTo(0, 0);
                } else {
                    pages[j].classList.remove('active');
                    navigationLinks[j].classList.remove('active');
                }
            }
        });
    }
});