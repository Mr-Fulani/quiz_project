/*
 * Вопрос задачи без картинки (см. task_question.css): подсветка кода, номера строк, набор текста,
 * когда карточка появляется на экране, и арабские вставки в своём направлении письма.
 * Решённые задачи и режим «уменьшить движение» показываются сразу, без набора.
 * Копия файла сайта: quiz_backend/blog/static/blog/js/task_question.js (менять оба).
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

    function whenVisible(element, callback) {
        if (!('IntersectionObserver' in window)) { callback(); return; }
        const observer = new IntersectionObserver(entries => {
            if (entries.some(e => e.isIntersecting)) { observer.disconnect(); callback(); }
        }, { threshold: 0.35 });
        observer.observe(element);
    }

    function setup(view) {
        if (view.dataset.tqReady) return;
        view.dataset.tqReady = '1';
        const item = view.closest('[data-task-id]');
        const animate = !reduceMotion && !(item && item.dataset.solved === 'true');

        if (view.dataset.kind === 'code') {
            const code = view.querySelector('.tq-code code') || view.querySelector('.tq-code');
            const source = code.textContent.replace(/\s+$/, '');
            const gutter = document.createElement('pre');
            gutter.className = 'tq-gutter';
            gutter.setAttribute('aria-hidden', 'true');
            gutter.textContent = source.split('\n').map((_, i) => i + 1).join('\n');
            view.querySelector('.tq-body').prepend(gutter);
            const html = highlightCode(source, view.dataset.language);
            if (animate) whenVisible(view, () => typeInto(code, html, true));
            else code.innerHTML = html;
        } else {
            const text = view.querySelector('.tq-text');
            if (!text) return;
            const html = markArabic(text.textContent.trim());
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

    // Mini App подменяет содержимое страницы своим загрузчиком — подхватываем новые карточки
    if ('MutationObserver' in window) {
        let scheduled = false;
        new MutationObserver(() => {
            if (scheduled) return;
            scheduled = true;
            requestAnimationFrame(() => { scheduled = false; init(); });
        }).observe(document.documentElement, { childList: true, subtree: true });
    }
})();
