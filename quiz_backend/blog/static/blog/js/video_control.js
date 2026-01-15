// static/js/video_control.js
'use strict';

document.addEventListener('DOMContentLoaded', function () {
    const pageElement = document.querySelector('[data-page]');
    if (!pageElement) return;
    
    const page = pageElement.dataset.page;
    const youtubeIframe = document.getElementById(`youtube-player-${page}`);
    const localVideo = document.getElementById(`local-video-${page}`);

    // Отладка: Проверяем, найдены ли элементы
    console.log(`Page: ${page}`);
    console.log(`YouTube iframe: ${youtubeIframe ? 'Found' : 'Not found'}`);
    console.log(`Local video: ${localVideo ? 'Found' : 'Not found'}`);

    // Функция для обработки ошибок YouTube видео (включая ошибку 153)
    function setupYouTubeErrorHandling(iframe, container) {
        if (!iframe || !container) return;

        const embedUrl = iframe.getAttribute('src');
        console.log('🎬 YouTube Video Error Handling Setup:', iframe.id || 'unknown iframe');

        // Извлекаем Video ID из URL
        const videoIdMatch = embedUrl.match(/embed\/([a-zA-Z0-9_-]+)/);
        if (!videoIdMatch) return;

        const videoId = videoIdMatch[1];
        const watchUrl = `https://www.youtube.com/watch?v=${videoId}`;
        let errorDetected = false;

        // Слушаем сообщения от YouTube
        const messageHandler = function(event) {
            if (event.origin.includes('youtube')) {
                const data = event.data;
                if (typeof data === 'string') {
                    try {
                        const parsed = JSON.parse(data);
                        if (parsed.event === 'onError' || parsed.info === 153) {
                            errorDetected = true;
                            showYouTubeFallback(container, watchUrl, videoId);
                        }
                    } catch (e) {}
                }
            }
        };

        window.addEventListener('message', messageHandler);

        // Fallback если видео не загрузилось за 5 секунд
        setTimeout(function() {
            if (!errorDetected) {
                // Проверяем видимость iframe
                const iframeRect = iframe.getBoundingClientRect();
                if (iframeRect.height === 0 || iframeRect.width === 0) {
                    console.warn('⚠️ YouTube iframe not loaded within 5 seconds');
                    showYouTubeFallback(container, watchUrl, videoId);
                }
            }
        }, 5000);

        function showYouTubeFallback(container, watchUrl, videoId) {
            console.error('❌ YouTube video embedding failed');
            console.log('📌 Possible reasons:');
            console.log('   1. Embedding disabled in video settings');
            console.log('   2. Video unavailable in your region');
            console.log('   3. Video is private or deleted');

            // Удаляем кнопку звука перед заменой контента
            const soundButton = container.querySelector('.video-sound-toggle');
            if (soundButton) {
                soundButton.remove();
            }

            container.innerHTML = `
                <div style="padding: 40px; text-align: center; background: #1a1a1a; border-radius: 8px; min-height: 300px; display: flex; flex-direction: column; justify-content: center; align-items: center;">
                    <svg style="width: 64px; height: 64px; margin-bottom: 20px; fill: #ff6b6b;" viewBox="0 0 24 24">
                        <path d="M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2M12,4C16.41,4 20,7.59 20,12C20,16.41 16.41,20 12,20C7.59,20 4,16.41 4,12C4,7.59 7.59,4 12,4M11,7V13H13V7H11M11,15V17H13V15H11Z" />
                    </svg>
                    <p style="color: #fff; margin-bottom: 20px; font-size: 16px;">Video embedding is restricted.</p>
                    <a href="${watchUrl}" target="_blank" rel="noopener noreferrer"
                       style="display: inline-block; padding: 12px 24px; background: #ff0000; color: #fff; text-decoration: none; border-radius: 5px; font-weight: 500;">
                        <svg style="width: 20px; height: 20px; margin-right: 8px; fill: currentColor; vertical-align: middle;" viewBox="0 0 24 24">
                            <path d="M10,15L15.19,12L10,9V15M21.56,7.17C21.69,7.64 21.78,8.27 21.84,9.07C21.91,9.87 21.94,10.56 21.94,11.16L22,12C22,14.19 21.84,15.8 21.56,16.83C21.31,17.73 20.73,18.31 19.83,18.56C19.36,18.69 18.5,18.78 17.18,18.84C15.88,18.91 14.69,18.94 13.59,18.94L12,19C7.81,19 5.2,18.84 4.17,18.56C3.27,18.31 2.69,17.73 2.44,16.83C2.31,16.36 2.22,15.73 2.16,14.93C2.09,14.13 2.06,13.44 2.06,12.84L2,12C2,9.81 2.16,8.2 2.44,7.17C2.69,6.27 3.27,5.69 4.17,5.44C4.64,5.31 5.5,5.22 6.82,5.16C8.12,5.09 9.31,5.06 10.41,5.06L12,5C16.19,5 18.8,5.16 19.83,5.44C20.73,5.69 21.31,6.27 21.56,7.17Z" />
                        </svg>
                        Watch on YouTube
                    </a>
                    <p style="color: #999; margin-top: 15px; font-size: 14px;">Video ID: ${videoId}</p>
                </div>
            `;
        }
    }

    // Функция создания кнопки включения звука
    function createSoundToggleButton(container, mediaElement, type = 'local') {
        // Проверяем, не создана ли уже кнопка
        if (container.querySelector('.video-sound-toggle')) {
            return;
        }

        const soundButton = document.createElement('button');
        soundButton.className = 'video-sound-toggle';
        soundButton.setAttribute('aria-label', 'Включить звук');
        soundButton.innerHTML = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z" fill="currentColor"/><line x1="2" y1="2" x2="22" y2="22" stroke="currentColor" stroke-width="2" stroke-linecap="round" class="mute-line"/></svg>';
        
        // Стили для кнопки (компактные размеры)
        const isMobile = window.innerWidth <= 580;
        const buttonSize = isMobile ? '32px' : '40px';
        const iconSize = isMobile ? '16px' : '20px';
        const topOffset = isMobile ? '8px' : '10px';
        const rightOffset = isMobile ? '8px' : '10px';
        
        Object.assign(soundButton.style, {
            position: 'absolute',
            top: topOffset,
            right: rightOffset,
            width: buttonSize,
            height: buttonSize,
            borderRadius: '50%',
            background: 'rgba(0, 0, 0, 0.7)',
            border: isMobile ? '1.5px solid rgba(255, 255, 255, 0.5)' : '2px solid rgba(255, 255, 255, 0.5)',
            color: '#fff',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: '10',
            transition: 'all 0.3s ease',
            padding: '0',
            outline: 'none',
            boxShadow: '0 3px 10px rgba(0, 0, 0, 0.4)',
            backdropFilter: 'blur(10px)',
            WebkitBackdropFilter: 'blur(10px)'
        });
        
        // Обновляем размер SVG иконки
        const svgElement = soundButton.querySelector('svg');
        if (svgElement) {
            svgElement.setAttribute('width', iconSize);
            svgElement.setAttribute('height', iconSize);
        }

        // Hover эффект
        soundButton.addEventListener('mouseenter', function() {
            this.style.background = 'rgba(0, 0, 0, 0.9)';
            this.style.borderColor = '#fff';
            this.style.transform = 'scale(1.1)';
        });
        soundButton.addEventListener('mouseleave', function() {
            if (mediaElement.muted || (type === 'youtube' && mediaElement.src && mediaElement.src.includes('mute=1'))) {
                this.style.background = 'rgba(0, 0, 0, 0.7)';
                this.style.borderColor = 'rgba(255, 255, 255, 0.5)';
            }
            this.style.transform = 'scale(1)';
        });

        // Обработчик клика
        soundButton.addEventListener('click', function(e) {
            e.stopPropagation();

            // Проверяем, существует ли еще mediaElement (не был ли заменен на fallback)
            if (!mediaElement || !mediaElement.parentNode || mediaElement.tagName !== (type === 'youtube' ? 'IFRAME' : 'VIDEO')) {
                console.log('Media element not found or replaced with fallback, removing sound button');
                soundButton.remove();
                return;
            }

            if (type === 'local') {
                if (mediaElement.muted) {
                    mediaElement.muted = false;
                    soundButton.querySelector('.mute-line').style.display = 'none';
                    soundButton.style.background = 'rgba(76, 175, 80, 0.9)';
                    soundButton.style.borderColor = '#4CAF50';
                    soundButton.setAttribute('aria-label', 'Выключить звук');
                } else {
                    mediaElement.muted = true;
                    soundButton.querySelector('.mute-line').style.display = 'block';
                    soundButton.style.background = 'rgba(0, 0, 0, 0.7)';
                    soundButton.style.borderColor = 'rgba(255, 255, 255, 0.5)';
                    soundButton.setAttribute('aria-label', 'Включить звук');
                }
                mediaElement.play().catch(e => console.log('Play prevented:', e));
            } else if (type === 'youtube') {
                const src = mediaElement.getAttribute('src');
                if (src && src.includes('mute=1')) {
                    const newSrc = src.replace('mute=1', 'mute=0');
                    mediaElement.setAttribute('src', newSrc);
                    soundButton.querySelector('.mute-line').style.display = 'none';
                    soundButton.style.background = 'rgba(76, 175, 80, 0.9)';
                    soundButton.style.borderColor = '#4CAF50';
                    soundButton.setAttribute('aria-label', 'Выключить звук');
                } else if (src && src.includes('mute=0')) {
                    const newSrc = src.replace('mute=0', 'mute=1');
                    mediaElement.setAttribute('src', newSrc);
                    soundButton.querySelector('.mute-line').style.display = 'block';
                    soundButton.style.background = 'rgba(0, 0, 0, 0.7)';
                    soundButton.style.borderColor = 'rgba(255, 255, 255, 0.5)';
                    soundButton.setAttribute('aria-label', 'Включить звук');
                }
            }
        });

        container.style.position = 'relative';
        container.appendChild(soundButton);
    }

    // Настройка автовоспроизведения и кеширования для всех локальных видео
    const allLocalVideos = document.querySelectorAll('video[autoplay][muted]');
    allLocalVideos.forEach(video => {
        // Находим родительский контейнер
        const container = video.closest('.video-banner-box') || video.parentElement;
        
        // Создаем кнопку включения звука
        createSoundToggleButton(container, video, 'local');

        // Убеждаемся что видео кешируется
        if (video.readyState >= 2) {
            // Видео уже загружено, можно воспроизводить
            video.play().catch(e => console.log('Autoplay prevented:', e));
        } else {
            // Ждем загрузки метаданных
            video.addEventListener('loadedmetadata', function() {
                video.play().catch(e => console.log('Autoplay prevented:', e));
            }, { once: true });
        }

        // При клике на видео - включаем звук (если видео было без звука)
        video.addEventListener('click', function(e) {
            // Не обрабатываем если клик по кнопке звука
            if (e.target.closest('.video-sound-toggle')) {
                return;
            }
            if (video.muted) {
                const soundButton = container.querySelector('.video-sound-toggle');
                if (soundButton) {
                    soundButton.click();
                }
            }
        });

        // Предзагрузка для кеширования
        video.load();
    });

    // Обработка видео в слайдерах (Swiper)
    const swiperVideos = document.querySelectorAll('.swiper-slide video[autoplay][muted]');
    swiperVideos.forEach(video => {
        // Находим контейнер в слайдере
        const container = video.closest('.swiper-slide') || video.closest('.media-wrapper') || video.parentElement;
        
        // Создаем кнопку включения звука
        createSoundToggleButton(container, video, 'local');
        
        // Предзагрузка для кеширования
        video.load();
    });

    // Функция проверки видимости элемента (с небольшим отступом)
    function isElementInViewport(el, threshold = 0.3) {
        const rect = el.getBoundingClientRect();
        const windowHeight = window.innerHeight || document.documentElement.clientHeight;
        const windowWidth = window.innerWidth || document.documentElement.clientWidth;
        
        // Элемент считается видимым если он находится в видимой области с учетом threshold
        return (
            rect.top < windowHeight * (1 + threshold) &&
            rect.bottom > -windowHeight * threshold &&
            rect.left < windowWidth &&
            rect.right > 0
        );
    }

    // Находим все видео на странице (включая YouTube iframes и локальные видео)
    const allVideoElements = [];
    
    // Добавляем YouTube iframes
    const allYoutubeIframes = document.querySelectorAll('iframe[src*="youtube"], iframe[src*="youtu.be"]');
    allYoutubeIframes.forEach(iframe => {
        // Находим родительский контейнер
        const container = iframe.closest('.video-banner-box') || iframe.parentElement;

        // Обрабатываем возможные ошибки YouTube (включая ошибку 153)
        setupYouTubeErrorHandling(iframe, container);

        // Создаем кнопку включения звука
        createSoundToggleButton(container, iframe, 'youtube');

        allVideoElements.push({
            element: iframe,
            type: 'youtube',
            isPlaying: false
        });
    });
    
    // Добавляем все локальные видео элементы для отслеживания
    const allLocalVideoElements = document.querySelectorAll('video');
    allLocalVideoElements.forEach(video => {
        // Пропускаем видео, которые уже обработаны выше (с autoplay и muted)
        // чтобы не дублировать обработчики событий
        if (!video.hasAttribute('autoplay') || !video.hasAttribute('muted')) {
            // Для видео без autoplay/muted тоже добавляем обработчик клика для звука
            if (video.muted) {
                video.addEventListener('click', function() {
                    if (video.muted) {
                        video.muted = false;
                        video.play().catch(e => console.log('Play with sound prevented:', e));
                    }
                });
            }
        }
        
        allVideoElements.push({
            element: video,
            type: 'local',
            isPlaying: false
        });
    });

    // Используем IntersectionObserver для более эффективного отслеживания видимости
    const observerOptions = {
        root: null,
        rootMargin: '-50px 0px -50px 0px', // Небольшой отступ чтобы паузить немного раньше
        threshold: [0, 0.1, 0.5, 1.0]
    };

    const videoObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            const videoData = entry.target.videoData;
            if (!videoData) return;

            // Если видео вышло из видимой области - ставим на паузу
            if (!entry.isIntersecting) {
                if (videoData.type === 'youtube') {
                    try {
                        const iframe = videoData.element;
                        // Пробуем использовать YouTube API для паузы
                        iframe.contentWindow?.postMessage('{"event":"command","func":"pauseVideo","args":""}', '*');
                        // Также убираем autoplay из URL чтобы видео не возобновлялось
                        const src = iframe.getAttribute('src');
                        if (src && src.includes('autoplay=1')) {
                            const newSrc = src.replace('autoplay=1', 'autoplay=0');
                            iframe.setAttribute('src', newSrc);
                        }
                        videoData.isPlaying = false;
                    } catch (e) {
                        // Если postMessage не работает, просто меняем URL
                        const src = videoData.element.getAttribute('src');
                        if (src && src.includes('autoplay=1')) {
                            const newSrc = src.replace('autoplay=1', 'autoplay=0');
                            videoData.element.setAttribute('src', newSrc);
                        }
                        videoData.isPlaying = false;
                    }
                } else if (videoData.type === 'local') {
                    const video = videoData.element;
                    if (!video.paused) {
                        video.pause();
                        videoData.isPlaying = false;
                    }
                }
            } else if (entry.isIntersecting && entry.intersectionRatio > 0.3) {
                // Если видео снова стало видимым - возобновляем (только для локальных видео)
                if (!videoData.isPlaying) {
                    if (videoData.type === 'local') {
                        const video = videoData.element;
                        if (video.paused && video.hasAttribute('autoplay')) {
                            video.play().catch(e => console.log('Resume play prevented:', e));
                            videoData.isPlaying = true;
                        }
                    }
                }
            }
        });
    }, observerOptions);

    // Регистрируем все видео в observer
    allVideoElements.forEach(videoData => {
        videoData.element.videoData = videoData;
        videoObserver.observe(videoData.element);
    });

    // Дополнительная обработка скролла (fallback для старых браузеров)
    let scrollTimeout;
    function throttledScrollHandler() {
        if (scrollTimeout) return;
        
        scrollTimeout = setTimeout(() => {
            scrollTimeout = null;
            
            // Проверяем все видео
            allVideoElements.forEach(videoData => {
                const el = videoData.element;
                const inView = isElementInViewport(el);
                
                if (!inView) {
                    if (videoData.type === 'youtube') {
                        try {
                            el.contentWindow?.postMessage('{"event":"command","func":"pauseVideo","args":""}', '*');
                            videoData.isPlaying = false;
                        } catch (e) {
                            // Игнорируем ошибки
                        }
                    } else if (videoData.type === 'local') {
                        if (!el.paused) {
                            el.pause();
                            videoData.isPlaying = false;
                        }
                    }
                }
            });
        }, 150);
    }

    // Пауза при скролле с throttling (fallback)
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