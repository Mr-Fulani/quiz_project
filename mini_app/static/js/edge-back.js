(function initEdgeBackGesture() {
    if (window.edgeBackGestureInitialized) return;
    window.edgeBackGestureInitialized = true;

    const TRIGGER_DISTANCE = 72;
    const FAST_SWIPE_DISTANCE = 36;
    const FAST_SWIPE_VELOCITY = 0.42;
    const MAX_DRAG_DISTANCE = 150;
    const DIRECTION_LOCK_DISTANCE = 7;

    let pointerId = null;
    let startX = 0;
    let startY = 0;
    let currentX = 0;
    let lastX = 0;
    let lastMoveTime = 0;
    let velocityX = 0;
    let horizontalGesture = false;
    let previewFrame = null;
    let pendingPreviewDistance = 0;
    let indicator = null;

    const hitArea = document.createElement('div');
    hitArea.className = 'edge-back-hit-area';
    hitArea.setAttribute('aria-hidden', 'true');
    document.body.appendChild(hitArea);

    function isHomePage() {
        return window.location.pathname === '/' || window.location.pathname === '/index';
    }

    function hasClosableOverlay() {
        return Boolean(
            document.querySelector('.selected-card-overlay.active') ||
            document.querySelector('#all-users-carousel.active') ||
            document.querySelector('.modal.show, .modal.active')
        );
    }

    function gestureIsAvailable() {
        return !isHomePage() || hasClosableOverlay();
    }

    function updateHitAreaAvailability() {
        hitArea.style.pointerEvents = gestureIsAvailable() ? 'auto' : 'none';
    }

    function ensureIndicator() {
        if (indicator?.isConnected) return indicator;

        indicator = document.createElement('div');
        indicator.className = 'edge-back-indicator';
        indicator.setAttribute('aria-hidden', 'true');
        indicator.innerHTML = '<span>‹</span>';
        document.body.appendChild(indicator);
        return indicator;
    }

    function renderPreview(distance) {
        const progress = Math.min(1, Math.max(0, distance / TRIGGER_DISTANCE));
        const offset = Math.min(MAX_DRAG_DISTANCE, Math.max(0, distance)) * 0.42;
        const content = document.querySelector('.content');
        const marker = ensureIndicator();

        marker.style.setProperty('--edge-back-progress', progress);
        marker.classList.toggle('ready', progress >= 1);

        if (content) {
            content.style.setProperty('--edge-back-offset', `${offset}px`);
            content.classList.add('edge-back-preview');
            content.classList.remove('edge-back-settling');
        }
    }

    function schedulePreview(distance) {
        pendingPreviewDistance = distance;
        if (previewFrame !== null) return;
        previewFrame = requestAnimationFrame(() => {
            previewFrame = null;
            renderPreview(pendingPreviewDistance);
        });
    }

    function clearIndicator() {
        if (!indicator) return;
        indicator.classList.remove('ready');
        indicator.style.removeProperty('--edge-back-progress');
        window.setTimeout(() => indicator?.remove(), 170);
    }

    function animatePreviewOut(completing, callback) {
        if (previewFrame !== null) {
            cancelAnimationFrame(previewFrame);
            previewFrame = null;
        }

        const content = document.querySelector('.content');
        if (!content) {
            clearIndicator();
            callback();
            return;
        }

        content.classList.add('edge-back-settling');
        content.style.setProperty(
            '--edge-back-offset',
            completing ? '88px' : '0px'
        );

        window.setTimeout(() => {
            content.classList.remove('edge-back-preview', 'edge-back-settling');
            content.style.removeProperty('--edge-back-offset');
            clearIndicator();
            callback();
        }, completing ? 130 : 170);
    }

    function triggerHaptic() {
        const haptic = window.Telegram?.WebApp?.HapticFeedback;
        if (haptic && typeof haptic.impactOccurred === 'function') {
            try {
                haptic.impactOccurred('medium');
                return;
            } catch (_) {}
        }
        if (typeof navigator.vibrate === 'function') {
            navigator.vibrate(24);
        }
    }

    function navigateBack() {
        triggerHaptic();

        if (document.querySelector('.selected-card-overlay.active') &&
            typeof window.goBackFromCard === 'function') {
            window.goBackFromCard();
            return;
        }

        if (document.querySelector('#all-users-carousel.active') &&
            typeof window.closeCarousel === 'function') {
            window.closeCarousel();
            return;
        }

        const activeModal = document.querySelector('.modal.show, .modal.active');
        if (activeModal) {
            const closeButton = activeModal.querySelector(
                '[data-dismiss="modal"], .close-modal, .modal-close, .close'
            );
            if (closeButton) {
                closeButton.click();
                return;
            }
        }

        if (window.location.pathname.includes('/subtopic/') &&
            window.location.pathname.includes('/tasks') &&
            typeof window.goBackFromTasks === 'function') {
            window.goBackFromTasks();
            return;
        }

        if (window.location.pathname.startsWith('/topic/') &&
            typeof window.goBackToMain === 'function') {
            window.goBackToMain();
            return;
        }

        if (window.history.length > 1) {
            window.history.back();
            return;
        }

        const lang = window.currentLanguage || document.documentElement.lang || 'en';
        const homeUrl = `/?lang=${encodeURIComponent(lang)}`;
        if (typeof window.loadPage === 'function') {
            window.loadPage(homeUrl);
        } else {
            window.location.href = homeUrl;
        }
    }

    function resetGesture() {
        pointerId = null;
        horizontalGesture = false;
        velocityX = 0;
    }

    function finishGesture(event, cancelled) {
        if (pointerId === null || event.pointerId !== pointerId) return;

        const distance = currentX - startX;
        const fastSwipe = distance >= FAST_SWIPE_DISTANCE && velocityX >= FAST_SWIPE_VELOCITY;
        const shouldGoBack = horizontalGesture &&
            !cancelled &&
            (distance >= TRIGGER_DISTANCE || fastSwipe);

        resetGesture();
        animatePreviewOut(shouldGoBack, () => {
            if (shouldGoBack) navigateBack();
        });
    }

    hitArea.addEventListener('pointerdown', (event) => {
        if (pointerId !== null || event.button > 0 || !gestureIsAvailable()) return;

        pointerId = event.pointerId;
        startX = event.clientX;
        startY = event.clientY;
        currentX = startX;
        lastX = startX;
        lastMoveTime = performance.now();
        velocityX = 0;
        horizontalGesture = false;

        if (hitArea.setPointerCapture) {
            hitArea.setPointerCapture(pointerId);
        }
    });

    hitArea.addEventListener('pointermove', (event) => {
        if (event.pointerId !== pointerId) return;

        const now = performance.now();
        const elapsed = Math.max(1, now - lastMoveTime);
        currentX = event.clientX;
        velocityX = Math.max(0, (currentX - lastX) / elapsed);
        lastX = currentX;
        lastMoveTime = now;

        const deltaX = currentX - startX;
        const deltaY = event.clientY - startY;

        if (!horizontalGesture) {
            if (Math.abs(deltaX) < DIRECTION_LOCK_DISTANCE &&
                Math.abs(deltaY) < DIRECTION_LOCK_DISTANCE) {
                return;
            }

            if (deltaX <= 0 || Math.abs(deltaY) > Math.abs(deltaX) * 1.1) {
                finishGesture(event, true);
                return;
            }

            horizontalGesture = true;
            ensureIndicator();
        }

        event.preventDefault();
        schedulePreview(deltaX);
    });

    hitArea.addEventListener('pointerup', (event) => finishGesture(event, false));
    hitArea.addEventListener('pointercancel', (event) => finishGesture(event, true));

    updateHitAreaAvailability();
    window.addEventListener('popstate', updateHitAreaAvailability);
    new MutationObserver(updateHitAreaAvailability).observe(document.body, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ['class']
    });
})();
