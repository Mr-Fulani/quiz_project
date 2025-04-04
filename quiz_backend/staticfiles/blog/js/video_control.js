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
        console.log(`Element rect: top=${rect.top}, bottom=${rect.bottom}, windowHeight=${windowHeight}`);
        return (
            rect.top >= 0 &&
            rect.bottom <= windowHeight
        );
    }

    // Пауза при скролле
    window.addEventListener('scroll', function () {
        console.log('Scroll event triggered');
        if (youtubeIframe) {
            const inView = isElementInViewport(youtubeIframe);
            console.log(`YouTube in view: ${inView}`);
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
            console.log(`Local video in view: ${inView}`);
            if (!inView) {
                localVideo.pause();
                console.log(`Local video paused on scroll out of view (${page})`);
            }
        }
    });

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