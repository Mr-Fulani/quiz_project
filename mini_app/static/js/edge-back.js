(function initEdgeBackGesture() {
    if (window.edgeBackGestureInitialized) return;
    window.edgeBackGestureInitialized = true;

    const EDGE_WIDTH = 28;
    const TRIGGER_DISTANCE = 82;
    const MAX_PREVIEW_DISTANCE = 110;
    const DIRECTION_LOCK_DISTANCE = 10;

    let pointerId = null;
    let startX = 0;
    let startY = 0;
    let currentX = 0;
    let horizontalGesture = false;
    let indicator = null;

    function isHomePage() {
        return window.location.pathname === '/' || window.location.pathname === '/index';
    }

    function isGestureBlocked(target) {
        return Boolean(target.closest('input, textarea, select, [contenteditable="true"]'));
    }

    function hasClosableOverlay() {
        return Boolean(
            document.querySelector('.selected-card-overlay.active') ||
            document.querySelector('#all-users-carousel.active') ||
            document.querySelector('.modal.show, .modal.active')
        );
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

    function updatePreview(distance) {
        const progress = Math.min(1, Math.max(0, distance / TRIGGER_DISTANCE));
        const previewDistance = Math.min(MAX_PREVIEW_DISTANCE, Math.max(0, distance));
        const content = document.querySelector('.content');
        const marker = ensureIndicator();

        marker.style.setProperty('--edge-back-progress', progress);
        marker.classList.toggle('ready', progress >= 1);

        if (content) {
            content.style.setProperty('--edge-back-offset', `${previewDistance * 0.22}px`);
            content.classList.add('edge-back-preview');
        }
    }

    function resetPreview() {
        const content = document.querySelector('.content');
        if (content) {
            content.classList.remove('edge-back-preview');
            content.style.removeProperty('--edge-back-offset');
        }

        if (indicator) {
            indicator.classList.remove('ready');
            indicator.style.removeProperty('--edge-back-progress');
            window.setTimeout(() => indicator?.remove(), 180);
        }
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

    function finishGesture(event, cancelled) {
        if (pointerId === null || event.pointerId !== pointerId) return;

        const distance = currentX - startX;
        const shouldGoBack = horizontalGesture && !cancelled && distance >= TRIGGER_DISTANCE;

        pointerId = null;
        horizontalGesture = false;
        resetPreview();

        if (shouldGoBack) {
            navigateBack();
        }
    }

    document.addEventListener('pointerdown', (event) => {
        if (pointerId !== null || event.button > 0) return;
        if (isHomePage() && !hasClosableOverlay()) return;
        if (event.clientX > EDGE_WIDTH || isGestureBlocked(event.target)) return;

        pointerId = event.pointerId;
        startX = event.clientX;
        startY = event.clientY;
        currentX = startX;
        horizontalGesture = false;
    }, true);

    document.addEventListener('pointermove', (event) => {
        if (event.pointerId !== pointerId) return;

        currentX = event.clientX;
        const deltaX = currentX - startX;
        const deltaY = event.clientY - startY;

        if (!horizontalGesture) {
            if (Math.abs(deltaX) < DIRECTION_LOCK_DISTANCE &&
                Math.abs(deltaY) < DIRECTION_LOCK_DISTANCE) {
                return;
            }

            if (deltaX <= 0 || Math.abs(deltaY) > Math.abs(deltaX)) {
                finishGesture(event, true);
                return;
            }

            horizontalGesture = true;
            ensureIndicator().classList.add('active');
        }

        event.preventDefault();
        updatePreview(deltaX);
    }, { capture: true, passive: false });

    document.addEventListener('pointerup', (event) => finishGesture(event, false), true);
    document.addEventListener('pointercancel', (event) => finishGesture(event, true), true);
})();
