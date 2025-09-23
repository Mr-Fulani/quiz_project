// static/js/video_control.js
'use strict';

document.addEventListener('DOMContentLoaded', function () {
    const page = document.querySelector('[data-page]').dataset.page;
    const youtubeIframe = document.getElementById(`youtube-player-${page}`);
    const localVideo = document.getElementById(`local-video-${page}`);

    // Отладка: Проверяем, найдены ли элементы
    console.log(`Page: ${page}`);
    console.log(`YouTube iframe: ${youtubeIframe ? 'Found' : 'Not found'}`);
    console.log(`Local video: ${localVideo ? 'Found' : 'Not found'}`);

    // Функция проверки видимости элемента
    function isElementInViewport(el) {
        const rect = el.getBoundingClientRect();
        const windowHeight = window.innerHeight || document.documentElement.clientHeight;
        return (
            rect.top >= 0 &&
            rect.bottom <= windowHeight
        );
    }

    // Throttling функция для оптимизации событий скролла
    let scrollTimeout;
    function throttledScrollHandler() {
        if (scrollTimeout) {
            return; // Игнорируем, если уже есть активный таймер
        }
        
        scrollTimeout = setTimeout(() => {
            scrollTimeout = null;
            handleScroll();
        }, 100); // Обрабатываем максимум 10 раз в секунду
    }
    
    function handleScroll() {
        if (youtubeIframe) {
            const inView = isElementInViewport(youtubeIframe);
            if (!inView) {
                try {
                    youtubeIframe.contentWindow.postMessage('{"event":"command","func":"pauseVideo","args":""}', '*');
                    console.log(`YouTube paused on scroll out of view (${page})`);
                } catch (e) {
                    console.error(`Error pausing YouTube on scroll (${page}):`, e);
                }
            }
        }
        if (localVideo && !localVideo.paused) {
            const inView = isElementInViewport(localVideo);
            if (!inView) {
                localVideo.pause();
                console.log(`Local video paused on scroll out of view (${page})`);
            }
        }
    }

    // Пауза при скролле с throttling
    window.addEventListener('scroll', throttledScrollHandler, { passive: true });

    // Пауза при переходе на другую страницу
    const navigationLinks = document.querySelectorAll('[data-nav-link]');
    navigationLinks.forEach(link => {
        link.addEventListener('click', function () {
            if (youtubeIframe) {
                try {
                    youtubeIframe.contentWindow.postMessage('{"event":"command","func":"pauseVideo","args":""}', '*');
                    console.log(`YouTube paused on navigation (${page})`);
                } catch (e) {
                    console.error(`Error pausing YouTube on navigation (${page}):`, e);
                }
            }
            if (localVideo && !localVideo.paused) {
                localVideo.pause();
                console.log(`Local video paused on navigation (${page})`);
            }
        });
    });
});