'use strict';

console.log("main.js loaded");

document.addEventListener('DOMContentLoaded', function () {
    console.log("DOMContentLoaded fired");

    const elementToggleFunc = function (elem) {
        elem.classList.toggle("active");
    }

    const sidebar = document.querySelector("[data-sidebar]");
    const sidebarBtn = document.querySelector("[data-sidebar-btn]");
    if (sidebarBtn) sidebarBtn.addEventListener("click", function () {
        elementToggleFunc(sidebar);
    });

    /**
     * Логика модального окна для видео.
     */
    const videoItems = document.querySelectorAll('[data-video-item]');
    const videoModalContainer = document.querySelector('[data-video-modal-container]');
    const videoCloseBtn = document.querySelector('[data-video-close-btn]');
    const videoOverlay = document.querySelector('[data-video-overlay]');
    const videoPlayer = document.querySelector('[data-video-player]');

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