// topic-cards.js
// Обработка карточек тем с увеличением на месте

console.log('🔥 TOPIC-CARDS.JS LOADED!');
console.log('Current page URL:', window.location.href);
console.log('DOM ready state:', document.readyState);

function initTopicCards() {
    console.log('🚀 Topic cards script initialized');
    
    // Определяем текущий язык из window (устанавливается в шаблоне)
    const currentLang = (typeof window.currentLanguage !== 'undefined') ? window.currentLanguage : (document.documentElement && document.documentElement.getAttribute('data-lang')) || 'en';

    // Проверяем DOM
    console.log('DOM ready state:', document.readyState);
    console.log('Current URL:', window.location.pathname);
    
    // Очищаем предыдущее состояние если оно есть
    if (window.galleryController && window.galleryController.resetState) {
        console.log('Resetting previous state...');
        window.galleryController.resetState();
    }
    
    // Получаем элементы галереи
    const gallery = document.querySelector('.gallery');
    const galleryContainer = document.querySelector('.gallery__container');
    const topicCards = document.querySelectorAll('.topic-card');
    
    console.log('Gallery elements check:');
    console.log('- gallery:', gallery ? '✅' : '❌');
    console.log('- galleryContainer:', galleryContainer ? '✅' : '❌');
    console.log('- topicCards count:', topicCards.length);
    
    if (!gallery || !galleryContainer || topicCards.length === 0) {
        console.log('❌ Gallery elements not found, skipping initialization');
        console.log('Available elements:', document.querySelectorAll('*').length, 'total elements in DOM');
        return;
    }
    
    // Применяем CSS-переменную индекса если она вынесена в data-attr
    topicCards.forEach(card => {
        const i = card.getAttribute('data-i');
        if (i !== null) {
            card.style.setProperty('--i', i);
        }

        card.setAttribute('draggable', 'false');
        card.querySelectorAll('img, video').forEach(media => {
            media.setAttribute('draggable', 'false');
        });
    });
    console.log('Found topic cards:', topicCards.length);
    
    let selectedCard = null;
    let selectedCardOverlay = null;
    
    // Переменная для хранения экземпляра Swiper
    let topicSwiper = null;
    
    // Создаем overlay при инициализации
    createSelectedCardOverlay();

    // Добавляем двустороннее управление основной 3D-каруселью свайпом.
    setupGallerySwipe();

    function setupGallerySwipe() {
        if (gallery.swipeCleanup) {
            gallery.swipeCleanup();
        }

        const cardCount = topicCards.length;
        const animation = galleryContainer.getAnimations().find(item =>
            item.animationName === 'rotate' ||
            (item.effect && item.effect.getTiming().duration)
        );

        if (!animation || cardCount < 2) {
            console.log('Gallery swipe skipped: rotation animation not found or too few cards');
            return;
        }

        const animationDuration = Number(animation.effect.getTiming().duration) || 20000;
        const cardRotationDegrees = 45;
        const cardStep = animationDuration * (cardRotationDegrees / 360);
        const millisecondsPerPixel = cardStep / 90;
        const dragThreshold = 8;
        const carouselPositions = Math.round(360 / cardRotationDegrees);
        let pointerId = null;
        let startX = 0;
        let startY = 0;
        let startTime = 0;
        let currentTime = 0;
        let desiredTime = 0;
        let horizontalDrag = false;
        let soundActive = false;
        let lastSoundPosition = null;
        let renderFrame = null;
        let settleFrame = null;
        let audioContext = null;
        let audioResumePromise = null;

        function normalizeTime(time) {
            return ((time % animationDuration) + animationDuration) % animationDuration;
        }

        function prepareClickSound() {
            const AudioContextClass = window.AudioContext || window.webkitAudioContext;
            if (!AudioContextClass) return;

            if (!audioContext) {
                audioContext = new AudioContextClass();
            }
            if (audioContext.state === 'suspended') {
                audioResumePromise = audioContext.resume()
                    .catch(() => null)
                    .finally(() => {
                        audioResumePromise = null;
                    });
            }
        }

        function emitClickSound() {
            if (!audioContext || audioContext.state !== 'running') return;

            const now = audioContext.currentTime;
            const masterGain = audioContext.createGain();
            const attack = audioContext.createOscillator();
            const attackGain = audioContext.createGain();
            const body = audioContext.createOscillator();
            const bodyGain = audioContext.createGain();

            masterGain.gain.setValueAtTime(0.75, now);
            masterGain.connect(audioContext.destination);

            // Короткая яркая атака делает щелчок хорошо различимым.
            attack.type = 'square';
            attack.frequency.setValueAtTime(1250, now);
            attack.frequency.exponentialRampToValueAtTime(620, now + 0.018);
            attackGain.gain.setValueAtTime(0.045, now);
            attackGain.gain.exponentialRampToValueAtTime(0.0001, now + 0.022);
            attack.connect(attackGain);
            attackGain.connect(masterGain);

            // Более низкий слой добавляет ощущение механического переключения.
            body.type = 'triangle';
            body.frequency.setValueAtTime(420, now);
            body.frequency.exponentialRampToValueAtTime(230, now + 0.035);
            bodyGain.gain.setValueAtTime(0.028, now);
            bodyGain.gain.exponentialRampToValueAtTime(0.0001, now + 0.04);
            body.connect(bodyGain);
            bodyGain.connect(masterGain);

            attack.start(now);
            attack.stop(now + 0.025);
            body.start(now);
            body.stop(now + 0.045);
        }

        function playClickSound() {
            if (!audioContext) {
                prepareClickSound();
            }

            if (audioContext?.state === 'running') {
                emitClickSound();
                return;
            }

            const resumePromise = audioResumePromise || audioContext?.resume();
            if (resumePromise && typeof resumePromise.then === 'function') {
                resumePromise.then(() => {
                    if (audioContext?.state === 'running') {
                        emitClickSound();
                    }
                }).catch(() => {});
            }
        }

        function playClickHaptic() {
            const hapticFeedback = window.Telegram?.WebApp?.HapticFeedback;

            if (hapticFeedback && typeof hapticFeedback.impactOccurred === 'function') {
                try {
                    hapticFeedback.impactOccurred('light');
                    return;
                } catch (error) {
                    console.debug('Telegram haptic feedback unavailable:', error);
                }
            }

            if (typeof navigator.vibrate === 'function') {
                navigator.vibrate(18);
            }
        }

        function updateClickSound(time) {
            if (!soundActive) return;

            const rawPosition = Math.round(time / cardStep);
            const position = ((rawPosition % carouselPositions) + carouselPositions) % carouselPositions;
            if (lastSoundPosition === null) {
                lastSoundPosition = position;
            } else if (position !== lastSoundPosition) {
                lastSoundPosition = position;
                playClickSound();
                playClickHaptic();
            }
        }

        function setAnimationTime(time) {
            currentTime = time;
            animation.currentTime = normalizeTime(time);
            updateClickSound(currentTime);
        }

        function renderTowardsDesiredTime() {
            renderFrame = null;
            const delta = desiredTime - currentTime;

            if (Math.abs(delta) < 0.5) {
                setAnimationTime(desiredTime);
                return;
            }

            setAnimationTime(currentTime + delta * 0.38);
            renderFrame = requestAnimationFrame(renderTowardsDesiredTime);
        }

        function setDesiredTime(time) {
            desiredTime = time;
            if (renderFrame === null) {
                renderFrame = requestAnimationFrame(renderTowardsDesiredTime);
            }
        }

        function settleToTime(targetTime, onComplete) {
            if (renderFrame !== null) {
                cancelAnimationFrame(renderFrame);
                renderFrame = null;
            }
            if (settleFrame !== null) {
                cancelAnimationFrame(settleFrame);
            }

            const fromTime = currentTime;
            const delta = targetTime - fromTime;
            const duration = Math.min(280, Math.max(150, Math.abs(delta / cardStep) * 190));
            const startedAt = performance.now();

            function settle(now) {
                const progress = Math.min(1, (now - startedAt) / duration);
                const easedProgress = 1 - Math.pow(1 - progress, 3);
                setAnimationTime(fromTime + delta * easedProgress);

                if (progress < 1) {
                    settleFrame = requestAnimationFrame(settle);
                } else {
                    settleFrame = null;
                    setAnimationTime(targetTime);
                    soundActive = false;
                    onComplete();
                }
            }

            settleFrame = requestAnimationFrame(settle);
        }

        function finishSwipe(event, cancelled = false) {
            if (pointerId === null || (event.pointerId !== undefined && event.pointerId !== pointerId)) {
                return;
            }

            const endX = event.clientX ?? startX;
            const deltaX = endX - startX;
            let targetTime = startTime;

            if (horizontalDrag && !cancelled) {
                const direction = deltaX === 0 ? 0 : Math.sign(deltaX);
                targetTime = Math.round(desiredTime / cardStep) * cardStep;

                // Даже короткий осознанный свайп должен переключить минимум одну карточку.
                if (Math.abs(deltaX) >= 30 && Math.abs(targetTime - startTime) < cardStep * 0.5) {
                    targetTime = startTime - direction * cardStep;
                }

                gallery.dataset.swipeClickBlockedUntil = String(Date.now() + 350);
            }

            gallery.classList.remove('dragging');
            pointerId = null;
            horizontalDrag = false;

            settleToTime(targetTime, () => {
                if (!selectedCard) {
                    animation.play();
                }
            });
        }

        function onPointerDown(event) {
            if (selectedCard || event.button > 0 || event.target.closest('button')) {
                return;
            }

            if (settleFrame !== null) {
                cancelAnimationFrame(settleFrame);
                settleFrame = null;
            }

            pointerId = event.pointerId;
            startX = event.clientX;
            startY = event.clientY;
            startTime = normalizeTime(Number(animation.currentTime) || 0);
            currentTime = startTime;
            desiredTime = startTime;
            horizontalDrag = false;
            soundActive = false;
            lastSoundPosition = null;
            animation.pause();
            prepareClickSound();
        }

        function onPointerMove(event) {
            if (event.pointerId !== pointerId) {
                return;
            }

            const deltaX = event.clientX - startX;
            const deltaY = event.clientY - startY;

            if (!horizontalDrag) {
                if (Math.abs(deltaX) < dragThreshold && Math.abs(deltaY) < dragThreshold) {
                    return;
                }

                if (Math.abs(deltaY) > Math.abs(deltaX)) {
                    finishSwipe(event, true);
                    return;
                }

                horizontalDrag = true;
                soundActive = true;
                lastSoundPosition = Math.round(currentTime / cardStep) % carouselPositions;
                gallery.classList.add('dragging');

                // Захватываем указатель только после распознавания свайпа.
                // При обычном тапе click должен остаться на самой карточке.
                if (gallery.setPointerCapture) {
                    gallery.setPointerCapture(pointerId);
                }
            }

            event.preventDefault();
            setDesiredTime(startTime - deltaX * millisecondsPerPixel);
        }

        function onPointerUp(event) {
            finishSwipe(event);
        }

        function onPointerCancel(event) {
            finishSwipe(event, true);
        }

        gallery.addEventListener('pointerdown', onPointerDown);
        gallery.addEventListener('pointermove', onPointerMove);
        gallery.addEventListener('pointerup', onPointerUp);
        gallery.addEventListener('pointercancel', onPointerCancel);
        gallery.addEventListener('dragstart', preventNativeDrag);

        function preventNativeDrag(event) {
            event.preventDefault();
        }

        gallery.swipeCleanup = function() {
            if (renderFrame !== null) cancelAnimationFrame(renderFrame);
            if (settleFrame !== null) cancelAnimationFrame(settleFrame);
            gallery.removeEventListener('pointerdown', onPointerDown);
            gallery.removeEventListener('pointermove', onPointerMove);
            gallery.removeEventListener('pointerup', onPointerUp);
            gallery.removeEventListener('pointercancel', onPointerCancel);
            gallery.removeEventListener('dragstart', preventNativeDrag);
        };

        console.log('✅ Bidirectional gallery swipe initialized');
    }
    
    // Создаем overlay для увеличенной карточки
    function createSelectedCardOverlay() {
        if (selectedCardOverlay) return selectedCardOverlay;
        
        selectedCardOverlay = document.createElement('div');
        selectedCardOverlay.className = 'selected-card-overlay';
        selectedCardOverlay.innerHTML = `
            <div class="selected-card-container">
                <!-- Содержимое будет вставлено динамически -->
            </div>
        `;
        
        // Закрытие по клику на фон
        selectedCardOverlay.addEventListener('click', function(e) {
            // Скрываем клавиатуру
            const searchInput = document.getElementById('search-input');
            if (searchInput) {
                searchInput.blur();
            }
            
            if (e.target === selectedCardOverlay) {
                goBackFromCard();
            }
        });
        
        document.body.appendChild(selectedCardOverlay);
        return selectedCardOverlay;
    }
    
    // Добавляем клавиатурное управление только для Escape
    document.addEventListener('keydown', function(e) {
        if (selectedCard && e.key === 'Escape') {
            goBackFromCard();
        }
    });

        // НОВЫЙ ПОДХОД: Используем делегирование событий на родительском контейнере
    // Это работает для всех карточек, включая динамически созданные
    
    // Удаляем старый обработчик если он есть
    if (gallery.clickHandlerAdded) {
        console.log('Removing old gallery click handler...');
        gallery.removeEventListener('click', gallery.clickHandler);
    }
    
    // Создаем новый обработчик
    gallery.clickHandler = function(e) {
        console.log('🔥 GALLERY CLICKED!', e.target);

        if (Number(gallery.dataset.swipeClickBlockedUntil || 0) > Date.now()) {
            e.preventDefault();
            e.stopPropagation();
            return;
        }
        
        // Скрываем клавиатуру при любом клике в галерее
        const searchInput = document.getElementById('search-input');
        if (searchInput) {
            searchInput.blur();
        }
        
        // Находим ближайшую карточку
        const clickedCard = e.target.closest('.topic-card');
        
        if (!clickedCard) {
            console.log('Clicked outside cards');
            return;
        }
        
        console.log('🎯 CARD FOUND!', clickedCard.getAttribute('data-topic-id'));
        
        // Если клик был на кнопке - игнорируем
        if (e.target.tagName === 'BUTTON' || e.target.closest('.share-topic-btn')) {
            console.log('Button clicked, ignoring...');
            return;
        }
        
        e.preventDefault();
        e.stopPropagation();
        
        const topicId = clickedCard.getAttribute('data-topic-id');
        console.log(`Clicked on topic card with ID: ${topicId}`);
        
        // Если карточка уже выбрана - ничего не делаем
        if (clickedCard.classList.contains('selected')) {
            console.log('Card already selected, ignoring...');
            return;
        }
        
        // Выбираем карточку
        console.log('Calling selectCard...');
        selectCard(clickedCard);
    };
    
    // Добавляем обработчик
    gallery.addEventListener('click', gallery.clickHandler);
    gallery.clickHandlerAdded = true;
    
    console.log('✅ Gallery click handler with delegation added');

    // Добавляем hover эффекты через делегирование
    if (!gallery.hoverHandlerAdded) {
        gallery.addEventListener('mouseenter', function(e) {
            const card = e.target.closest('.topic-card');
            if (card && !selectedCard && !('ontouchstart' in window)) {
                pauseGallery();
            }
        }, true);

        gallery.addEventListener('mouseleave', function(e) {
            const card = e.target.closest('.topic-card');
            if (card && !selectedCard && !('ontouchstart' in window)) {
                setTimeout(() => {
                    if (!selectedCard) {
                        resumeGallery();
                    }
                }, 500);
            }
        }, true);
        
        gallery.hoverHandlerAdded = true;
        console.log('✅ Gallery hover handlers added');
    }
    
    // Функции управления
    function selectCard(card) {
        console.log('Selecting card:', card.getAttribute('data-topic-id'));
        
        // Убираем предыдущий выбор
        if (selectedCard) {
            selectedCard.classList.remove('selected');
        }
        
        // Выбираем новую карточку
        selectedCard = card;
        
        // Получаем индекс выбранной карточки
        const cardIndex = parseInt(card.getAttribute('data-i') || '0', 10);
        
        // Останавливаем галерею
        pauseGallery();
        
        // Добавляем класс выбора к оригинальной карточке (делает её полупрозрачной)
        card.classList.add('selected');
        galleryContainer.classList.add('has-selection');
        
        // Создаем overlay и показываем Swiper с возможностью свайпа
        const overlay = createSelectedCardOverlay();
        const container = overlay.querySelector('.selected-card-container');
        
        // Создаем структуру Swiper со всеми карточками
        let swiperHTML = `
            <div class="swiper" id="topic-cards-swiper">
                <div class="swiper-wrapper">
        `;
        
        // Добавляем все карточки в Swiper
        topicCards.forEach((topicCard, index) => {
            const mediaType = topicCard.getAttribute('data-media-type') || 'default';
            const title = topicCard.querySelector('.card-overlay h3').textContent;
            const topicId = topicCard.getAttribute('data-topic-id');
            
            // Получаем медиа-элемент (img или video)
            let mediaElement = '';
            if (mediaType === 'video') {
                // Для видео всегда показываем само видео в увеличенной карточке
                const video = topicCard.querySelector('video');
                const poster = topicCard.querySelector('img.video-poster');
                
                // Получаем URL видео из data-атрибута или из src видео
                let videoSrc = topicCard.getAttribute('data-video-url');
                if (!videoSrc && video) {
                    videoSrc = video.src;
                }
                
                if (videoSrc) {
                    // Видео без стандартных контролов и без звука по умолчанию
                    mediaElement = `<video src="${videoSrc}" alt="${title}" playsinline muted loop></video>`;
                }
            } else {
                const img = topicCard.querySelector('img');
                if (img && !img.classList.contains('video-poster')) {
                    mediaElement = `<img src="${img.src}" alt="${img.alt}">`;
                }
            }
            
            // Добавляем кнопку звука только для видео
            const soundButtonHTML = mediaType === 'video' ? `
                <button class="sound-toggle-btn" data-video-index="${index}">
                    <ion-icon name="volume-mute-outline"></ion-icon>
                </button>
            ` : '';
            
            swiperHTML += `
                <div class="swiper-slide">
                    <div class="topic-card-enlarged">
                        <button class="share-topic-btn" data-topic-id="${topicId}" data-topic-name="${title}" data-lang="${currentLang}">
                            <ion-icon name="share-social-outline"></ion-icon>
                        </button>
                        ${mediaElement}
                        ${soundButtonHTML}
                        <div class="card-overlay always-visible">
                            <h3>${title}</h3>
                            <div class="card-actions">
                                <button class="btn-start" onclick="handleStartTopic(event, ${topicId})">Начать</button>
                                <button class="btn-back" onclick="goBackFromCard(event)">Назад</button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        });
        
        swiperHTML += `
                </div>
                <!-- Навигация -->
                <div class="swiper-button-next"></div>
                <div class="swiper-button-prev"></div>
            </div>
        `;
        
        container.innerHTML = swiperHTML;
        
        // Показываем overlay
        setTimeout(() => {
            overlay.classList.add('active');
        }, 50);
        
        // Инициализируем Swiper после показа overlay
        setTimeout(() => {
            if (typeof Swiper !== 'undefined') {
                console.log('Инициализируем Swiper на слайде:', cardIndex);
                
                // Уничтожаем предыдущий экземпляр Swiper если есть
                if (topicSwiper) {
                    topicSwiper.destroy(true, true);
                }
                
                topicSwiper = new Swiper('#topic-cards-swiper', {
                    slidesPerView: 1,
                    spaceBetween: 0,
                    centeredSlides: true,
                    loop: false,
                    effect: 'slide',
                    speed: 300,
                    initialSlide: cardIndex, // Начинаем с выбранной карточки
                    navigation: {
                        nextEl: '.swiper-button-next',
                        prevEl: '.swiper-button-prev',
                    },
                    on: {
                        init: function() {
                            console.log('Swiper инициализирован на слайде:', this.activeIndex);
                            // Автовоспроизведение видео на текущем слайде (без звука)
                            const activeSlide = this.slides[this.activeIndex];
                            if (activeSlide) {
                                const video = activeSlide.querySelector('video');
                                if (video) {
                                    video.muted = true; // Без звука по умолчанию
                                    video.play().catch(err => console.log('Autoplay blocked:', err));
                                    updateSoundButton(activeSlide, video);
                                }
                            }
                        },
                        slideChange: function() {
                            // Останавливаем видео на предыдущем слайде
                            const previousSlide = this.slides[this.previousIndex];
                            if (previousSlide) {
                                const prevVideo = previousSlide.querySelector('video');
                                if (prevVideo) {
                                    prevVideo.pause();
                                    prevVideo.muted = true; // Отключаем звук при смене слайда
                                    updateSoundButton(previousSlide, prevVideo);
                                }
                            }
                            
                            // Автовоспроизведение видео при смене слайда (без звука)
                            const activeSlide = this.slides[this.activeIndex];
                            if (activeSlide) {
                                const video = activeSlide.querySelector('video');
                                if (video) {
                                    video.muted = true; // Без звука по умолчанию
                                    video.play().catch(err => console.log('Autoplay blocked:', err));
                                    updateSoundButton(activeSlide, video);
                                }
                            }
                        }
                    }
                });
                
                // Добавляем обработчики для кнопок звука
                setupSoundButtons();
                
                console.log('Swiper карточек тем успешно инициализирован');
            } else {
                console.error('Swiper библиотека не найдена! Убедитесь, что Swiper.js подключен.');
            }
        }, 100);
        
        console.log('Card selected successfully with Swiper support');
    }

    // Убрали прогресс из overlay карточки по требованию
    
    function goBackFromCard() {
        console.log('Going back from selected card');
        
        // Уничтожаем Swiper если он существует
        if (topicSwiper) {
            console.log('Уничтожаем Swiper перед закрытием');
            topicSwiper.destroy(true, true);
            topicSwiper = null;
        }
        
        // Скрываем overlay
        if (selectedCardOverlay) {
            selectedCardOverlay.classList.remove('active');
        }
        
        // Убираем выбор с карточки
        if (selectedCard) {
            selectedCard.classList.remove('selected');
            selectedCard = null;
        }
        
        galleryContainer.classList.remove('has-selection');
        
        // Возобновляем галерею с того же места
        resumeGallery();
        
        console.log('Returned to gallery');
    }
    
    function pauseGallery() {
        console.log('Pausing gallery');
        gallery.classList.add('paused');
    }
    
    function resumeGallery() {
        console.log('Resuming gallery');
        gallery.classList.remove('paused');
    }
    
    // Функция для настройки кнопок звука
    function setupSoundButtons() {
        const soundButtons = document.querySelectorAll('.sound-toggle-btn');
        soundButtons.forEach(button => {
            button.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                
                const slide = this.closest('.swiper-slide');
                const video = slide.querySelector('video');
                if (video) {
                    video.muted = !video.muted;
                    updateSoundButton(slide, video);
                }
            });
        });
    }
    
    // Функция для обновления иконки кнопки звука
    function updateSoundButton(slide, video) {
        const soundButton = slide.querySelector('.sound-toggle-btn');
        if (soundButton) {
            const icon = soundButton.querySelector('ion-icon');
            if (icon) {
                if (video.muted) {
                    icon.setAttribute('name', 'volume-mute-outline');
                } else {
                    icon.setAttribute('name', 'volume-high-outline');
                }
            }
        }
    }
    
    function navigateToTopic(topicId) {
        console.log(`Navigating to topic: ${topicId}`);
        
        // Используем AJAX навигацию вместо полной перезагрузки страницы
        setTimeout(async () => {
            try {
                const url = `/topic/${topicId}?lang=${encodeURIComponent(currentLang)}`;
                console.log('Loading topic page via AJAX:', url);
                
                // Сначала сбрасываем состояние галереи
                if (window.galleryController && window.galleryController.resetState) {
                    window.galleryController.resetState();
                }
                
                const contentContainer = document.querySelector('.content');
                if (!contentContainer) {
                    console.log('Content container not found, falling back to normal navigation');
                    window.location.href = url;
                    return;
                }
                
                // Показываем индикатор загрузки
                contentContainer.style.opacity = '0.7';
                
                const response = await fetch(url, {
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });
                
                if (response.ok) {
                    const html = await response.text();
                    
                    // Парсим HTML и извлекаем контент
                    const parser = new DOMParser();
                    const doc = parser.parseFromString(html, 'text/html');
                    const newContent = doc.querySelector('.content');
                    
                    if (newContent) {
                        // Плавно заменяем контент
                        setTimeout(() => {
                            contentContainer.innerHTML = newContent.innerHTML;
                            contentContainer.style.opacity = '1';
                            
                            // Обновляем URL в браузере
                            window.history.pushState({}, '', url);
                            
                            // Обновляем активную навигацию
                            updateActiveNavigation(url);
                            
                            // Загружаем скрипт для страницы темы
                            loadTopicDetailScript();
                            
                            console.log('Topic page loaded via AJAX successfully');
                        }, 200);
                    } else {
                        console.log('New content not found, falling back to normal navigation');
                        window.location.href = url;
                    }
                } else {
                    console.log('AJAX request failed, falling back to normal navigation');
                    window.location.href = url;
                }
            } catch (error) {
                console.error('Error during AJAX navigation:', error);
                // Fallback к обычному переходу
                window.location.href = `/topic/${topicId}?lang=${encodeURIComponent(window.currentLanguage || document.documentElement.lang || 'en')}`;
            }
        }, 300);
    }
    
    // Функция для обновления активной навигации
    function updateActiveNavigation(url) {
        const navItems = document.querySelectorAll('.navigation .list');
        navItems.forEach(item => {
            item.classList.remove('active');
            // Для страниц тем активируем "Главная"
            if (url.startsWith('/topic/') && item.getAttribute('data-href') === '/') {
                item.classList.add('active');
            }
        });
    }
    
    // Функция для динамической загрузки скрипта страницы темы
    function loadTopicDetailScript() {
        console.log('📜 Loading topic detail script...');
        
        // Удаляем предыдущий скрипт если он есть
        const existingScript = document.getElementById('topic-detail-script');
        if (existingScript) {
            existingScript.remove();
        }
        
        // Создаем новый скрипт
        const script = document.createElement('script');
        script.id = 'topic-detail-script';
        script.src = '/static/js/topic-detail.js';
        script.onload = function() {
            console.log('✅ Topic detail script loaded successfully');
        };
        script.onerror = function() {
            console.error('❌ Failed to load topic detail script');
        };
        
        document.head.appendChild(script);
    }
    
    // Экспортируем функции для использования в HTML
    window.selectCard = selectCard;
    window.goBackFromCard = function(event) {
        if (event) {
            event.preventDefault();
                    event.stopPropagation();
    }
    goBackFromCard();
};
    window.startTopic = function(event, topicId) {
        if (event) {
            event.preventDefault();
            event.stopPropagation();
        }
        navigateToTopic(topicId);
    };
    
    // Экспортируем функции глобально для экстренного доступа
    window.handleStartTopic = function(event, topicId) {
        if (event) {
            event.preventDefault();
            event.stopPropagation();
        }
        navigateToTopic(topicId);
    };
    
    // Объект для управления галереей
    window.galleryController = {
        selectCard,
        goBackFromCard,
        pauseGallery,
        resumeGallery,
        navigateToTopic,
        // Функция сброса состояния для AJAX навигации
        resetState: function() {
            console.log('Resetting gallery state...');
            
            try {
                // Скрываем клавиатуру
                const searchInput = document.getElementById('search-input');
                if (searchInput) {
                    searchInput.blur();
                }
                
                // Сбрасываем выбранную карточку
                if (selectedCard) {
                    selectedCard.classList.remove('selected');
                    selectedCard = null;
                }
                
                // Убираем overlay если он активен
                if (selectedCardOverlay) {
                    selectedCardOverlay.classList.remove('active');
                    // Небольшая задержка перед удалением для анимации
                    setTimeout(() => {
                        if (selectedCardOverlay && selectedCardOverlay.parentNode) {
                            selectedCardOverlay.remove();
                        }
                        selectedCardOverlay = null;
                    }, 100);
                }
                
                // Убираем все overlay-элементы на всякий случай
                const allOverlays = document.querySelectorAll('.selected-card-overlay');
                allOverlays.forEach(overlay => {
                    overlay.classList.remove('active');
                    setTimeout(() => overlay.remove(), 100);
                });
                
                // Убираем класс выбора с контейнера
                const currentGalleryContainer = document.querySelector('.gallery__container');
                if (currentGalleryContainer) {
                    currentGalleryContainer.classList.remove('has-selection');
                }
                
                // Убираем классы выбора со всех карточек
                const allCards = document.querySelectorAll('.topic-card.selected');
                allCards.forEach(card => card.classList.remove('selected'));
                
                // Возобновляем галерею
                const currentGallery = document.querySelector('.gallery');
                if (currentGallery) {
                    currentGallery.classList.remove('paused');
                }
                
                console.log('Gallery state reset complete (delegation preserved)');
            } catch (error) {
                console.error('Error during state reset:', error);
            }
        },
        // Диагностическая функция
        debug: function() {
            console.log('=== Gallery Debug Info ===');
            console.log('Selected card:', selectedCard?.getAttribute('data-topic-id') || 'none');
            console.log('Gallery classes:', gallery?.className);
            console.log('Gallery container classes:', galleryContainer?.className);
            console.log('========================');
        }
    };
    
    console.log('Gallery controller initialized');
    console.log('Используйте window.galleryController.debug() для диагностики');
    
    // Проверяем, что карточки найдены
    console.log('Found topic cards:', topicCards.length);
    
    // Добавляем тестовую функцию для диагностики
    window.testCardClick = function(cardIndex = 0) {
        const cards = document.querySelectorAll('.topic-card');
        if (cards[cardIndex]) {
            console.log('Testing click on card:', cardIndex);
            cards[cardIndex].click();
        } else {
            console.log('Card not found:', cardIndex);
        }
    };
    
    console.log('💡 Для тестирования кликов используйте: window.testCardClick(0)');
    console.log('✅ Gallery initialization complete with event delegation');
}

// Функция для загрузки данных темы через API
async function loadTopicData(topicId) {
    try {
        const response = await fetch(`/api/topic/${topicId}`);
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Error loading topic data:', error);
        return null;
    }
}

// ЭКСТРЕННЫЙ ФИКС: Добавляем глобальный обработчик кликов
console.log('🚨 Adding emergency global click handler...');

document.addEventListener('click', function(e) {
    console.log('🔥 GLOBAL CLICK:', e.target);
    
    // Проверяем, находимся ли мы на странице темы
    const isTopicPage = window.location.pathname.startsWith('/topic/');
    if (isTopicPage) {
        console.log('🚫 On topic page, ignoring global click handler');
        return;
    }
    
    const card = e.target.closest('.topic-card');
    if (card) {
        const cardGallery = card.closest('.gallery');
        if (cardGallery && Number(cardGallery.dataset.swipeClickBlockedUntil || 0) > Date.now()) {
            e.preventDefault();
            e.stopPropagation();
            return;
        }

        console.log('🎯 CARD DETECTED GLOBALLY!', card.getAttribute('data-topic-id'));
        
        // Скрываем клавиатуру
        const searchInput = document.getElementById('search-input');
        if (searchInput) {
            searchInput.blur();
        }
        
        // Если клик на кнопке - игнорируем
        if (e.target.tagName === 'BUTTON' || e.target.closest('.share-topic-btn')) {
            console.log('Button clicked, ignoring...');
            return;
        }
        
        e.preventDefault();
        e.stopPropagation();
        
        // Если карточка уже выбрана - ничего не делаем
        if (card.classList.contains('selected')) {
            console.log('Card already selected, ignoring...');
            return;
        }
        
        // Вызываем функцию выбора карточки
        if (window.galleryController && window.galleryController.selectCard) {
            console.log('Calling selectCard via galleryController...');
            window.galleryController.selectCard(card);
        } else {
            console.log('⚠️ galleryController not found, trying direct call...');
            // Прямой вызов функции selectCard
            if (typeof selectCard === 'function') {
                selectCard(card);
            } else {
                console.error('❌ selectCard function not available!');
            }
        }
    }
}, true); // Используем capture phase

console.log('✅ Emergency global click handler added');

// Экспортируем функцию глобально для доступа из других скриптов
window.initTopicCards = initTopicCards;
// goBackFromCard уже экспортирована выше (строка 537), не экспортируем повторно
if (typeof window.goBackFromCard === 'undefined') {
    window.goBackFromCard = goBackFromCard;
}

// Инициализируем при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    console.log('🔥 DOMContentLoaded fired!');
    initTopicCards();
});

// Дополнительная инициализация для случаев когда DOM уже готов
if (document.readyState === 'loading') {
    console.log('⏳ DOM still loading, waiting for DOMContentLoaded...');
} else {
    console.log('✅ DOM already ready, initializing immediately...');
    initTopicCards();
}

console.log('🔥 TOPIC-CARDS.JS SCRIPT END REACHED!');
