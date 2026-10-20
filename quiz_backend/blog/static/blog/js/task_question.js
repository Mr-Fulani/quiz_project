/*
 * Вопрос задачи без картинки (см. task_question.css): подсветка кода, номера строк, набор текста,
 * когда карточка появляется на экране, и арабские вставки в своём направлении письма.
 * Решённые задачи и режим «уменьшить движение» показываются сразу, без набора.
 * Копия для Mini App: mini_app/static/js/task-question.js (менять оба).
 */
(function () {
    'use strict';

    // Скрипт может подключиться повторно (Mini App подгружает страницы без перезагрузки)
    if (window.TaskQuestion) { window.TaskQuestion.init(); return; }

    const AR_CHARS = '؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿';
    const AR_RUN = new RegExp('([' + AR_CHARS + '](?:[' + AR_CHARS + '\\s]*[' + AR_CHARS + '])?)', 'g');
    const AR_ONLY = new RegExp('^[\\s' + AR_CHARS + ']+$');
    const reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const segmenter = window.Intl && Intl.Segmenter ? new Intl.Segmenter(undefined, { granularity: 'grapheme' }) : null;

    const escapeHtml = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    const graphemes = s => (segmenter ? Array.from(segmenter.segment(s), x => x.segment) : Array.from(s));

    function highlightCode(code, language) {
        try {
            if (window.hljs && language && window.hljs.getLanguage(language)) {
                return window.hljs.highlight(code, { language: language, ignoreIllegals: true }).value;
            }
        } catch (e) { /* без подсветки */ }
        return escapeHtml(code);
    }

    // Арабская вставка изолируется в своём направлении; короткая фраза с кавычками не разрывается
    function markArabic(text) {
        return escapeHtml(text)
            .replace(AR_RUN, m => '<span class="tq-ar' + (m.length <= 28 ? ' tq-nobr' : '') + '" lang="ar" dir="rtl">' + m + '</span>')
            .replace(/([«“"])(<span class="tq-ar tq-nobr"[^>]*>[^<]*<\/span>)([»”"])/g, '<span class="tq-nobr">$1$2$3</span>');
    }

    function typeInto(target, html, animate) {
        target.innerHTML = html;
        const caret = document.createElement('span');
        caret.className = 'tq-caret';
        if (!animate) return;
        const nodes = [];
        const walker = document.createTreeWalker(target, NodeFilter.SHOW_TEXT);
        while (walker.nextNode()) nodes.push(walker.currentNode);
        const full = nodes.map(n => graphemes(n.data));
        nodes.forEach(n => { n.data = ''; });
        let ni = 0;
        let gi = 0;
        (function step() {
            while (ni < nodes.length && gi >= full[ni].length) { ni++; gi = 0; }
            if (ni >= nodes.length) { target.appendChild(caret); return; }
            const chars = full[ni];
            let take = 1;
            // отступы набираются сразу, как автоотступ в редакторе
            while (gi + take < chars.length && chars[gi] === ' ' && chars[gi + take] === ' ') take++;
            while (gi + take < chars.length && chars[gi + take - 1] === '\n' && chars[gi + take] === ' ') take++;
            gi += take;
            nodes[ni].data = chars.slice(0, gi).join('');
            nodes[ni].parentNode.insertBefore(caret, nodes[ni].nextSibling);
            setTimeout(step, chars[gi - 1] === '\n' ? 160 : 22 + Math.random() * 28);
        })();
    }

    // Набор начинается, когда карточка видна на экране. Кроме IntersectionObserver — запасная проверка
    // по прокрутке (любого контейнера) и размеру окна: в некоторых WebView наблюдатель не срабатывает
    const waiting = new Set();
    function isVisible(element) {
        const rect = element.getBoundingClientRect();
        const visible = Math.min(rect.bottom, window.innerHeight) - Math.max(rect.top, 0);
        return rect.height > 0 && visible >= Math.min(rect.height, window.innerHeight) * 0.35;
    }
    function checkWaiting() {
        waiting.forEach(entry => {
            if (!entry.element.isConnected) waiting.delete(entry);  // карточку убрал загрузчик страниц
            else if (isVisible(entry.element)) entry.start();
        });
    }
    function whenVisible(element, callback) {
        let started = false;
        const entry = { element: element, start: null };
        const observer = 'IntersectionObserver' in window ? new IntersectionObserver(entries => {
            if (entries.some(e => e.isIntersecting)) entry.start();
        }, { threshold: 0.35 }) : null;
        entry.start = () => {
            if (started) return;
            started = true;
            waiting.delete(entry);
            if (observer) observer.disconnect();
            callback();
        };
        waiting.add(entry);
        if (observer) observer.observe(element);
        if (isVisible(element)) entry.start();
    }
    document.addEventListener('scroll', checkWaiting, { capture: true, passive: true });
    window.addEventListener('resize', checkWaiting, { passive: true });

    // Подсветка нужна только при коде: highlight.js подгружается по требованию
    // (в Mini App страницы задач открываются загрузчиком без отдельного <script>)
    const HLJS_URL = 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js';
    let hljsLoading = null;
    function withHighlighter(callback) {
        if (window.hljs) { callback(); return; }
        if (!hljsLoading) {
            hljsLoading = new Promise(resolve => {
                const script = document.createElement('script');
                script.src = HLJS_URL;
                script.onload = script.onerror = () => resolve();
                document.head.appendChild(script);
            });
        }
        hljsLoading.then(callback);
    }

    // Обработанные карточки помним по самим элементам, а не по атрибуту: если страница
    // перерисует разметку (копия получит атрибуты), новая карточка обработается заново
    const processed = new WeakSet();

    function setup(view) {
        if (processed.has(view)) return;
        processed.add(view);
        const item = view.closest('[data-task-id]');
        const animate = !reduceMotion && !(item && item.dataset.solved === 'true');

        if (view.dataset.kind === 'code') {
            const code = view.querySelector('.tq-code code') || view.querySelector('.tq-code');
            // Исходный текст — из атрибута, если карточку уже обрабатывали (текст мог быть недонабран)
            const source = view.dataset.tqSource || code.textContent.replace(/\s+$/, '');
            view.dataset.tqSource = source;
            view.querySelectorAll('.tq-gutter').forEach(g => g.remove());
            const gutter = document.createElement('pre');
            gutter.className = 'tq-gutter';
            gutter.setAttribute('aria-hidden', 'true');
            gutter.textContent = source.split('\n').map((_, i) => i + 1).join('\n');
            view.querySelector('.tq-body').prepend(gutter);
            withHighlighter(() => {
                const html = highlightCode(source, view.dataset.language);
                if (animate) whenVisible(view, () => typeInto(code, html, true));
                else code.innerHTML = html;
            });
        } else {
            const text = view.querySelector('.tq-text');
            if (!text) return;
            const source = view.dataset.tqSource || text.textContent.trim();
            view.dataset.tqSource = source;
            const html = markArabic(source);
            if (animate) whenVisible(view, () => typeInto(text, html, true));
            else text.innerHTML = html;
        }

        // Варианты ответа целиком на арабском — арабским шрифтом и справа налево
        if (item) {
            item.querySelectorAll('.answer-option, .quiz-option').forEach(option => {
                const value = option.textContent.trim();
                if (value && AR_ONLY.test(value)) {
                    option.classList.add('tq-ar-answer');
                    option.setAttribute('lang', 'ar');
                    option.setAttribute('dir', 'rtl');
                }
            });
        }
    }

    function init(root) {
        (root || document).querySelectorAll('.tq[data-kind]').forEach(setup);
    }

    window.TaskQuestion = { init: init };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => init());
    else init();

    // Mini App подменяет содержимое страницы своим загрузчиком — подхватываем новые карточки.
    // setTimeout, а не requestAnimationFrame: тот не срабатывает в неактивной вкладке
    if ('MutationObserver' in window) {
        let scheduled = false;
        new MutationObserver(() => {
            if (scheduled) return;
            scheduled = true;
            setTimeout(() => { scheduled = false; init(); }, 30);
        }).observe(document.documentElement, { childList: true, subtree: true });
    }
})();
