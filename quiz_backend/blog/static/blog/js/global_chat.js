document.addEventListener('DOMContentLoaded', () => {
    const config = window.globalChatConfig;
    if (!config) {
        return;
    }

    const feed = document.getElementById('global-chat-feed');
    const form = document.getElementById('global-chat-form');
    const input = document.getElementById('global-chat-input');
    const replyBox = document.getElementById('global-chat-reply');
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
    let sinceCursor = null;
    let isInitialLoad = true;
    const language = document.documentElement.lang || 'en';
    let replyToMessage = null;

    const showNotice = (text, type = 'success') => {
        const notification = document.createElement('div');
        notification.className = `message-notification ${type}`;
        notification.textContent = text;
        document.body.appendChild(notification);
        setTimeout(() => notification.remove(), 2600);
    };

    const apiFetch = (url, options = {}) => {
        const headers = options.headers || {};
        if (csrfToken) {
            headers['X-CSRFToken'] = csrfToken;
        }
        headers['X-Requested-With'] = 'XMLHttpRequest';
        return fetch(url, { ...options, headers });
    };

    const getDeleteUrl = (messageId) => config.deleteUrlTemplate.replace('/0/', `/${messageId}/`);
    const getBanUrl = (userId) => config.banUrlTemplate.replace('/0/', `/${userId}/`);
    const getUnbanUrl = (userId) => config.unbanUrlTemplate.replace('/0/', `/${userId}/`);

    const renderEmpty = () => {
        feed.innerHTML = `<div class="global-chat-empty">${config.texts.empty}</div>`;
    };

    const escapeHtml = (text) => {
        return String(text || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    };

    const showBanOverlay = (banData) => {
        const existing = document.querySelector('.ban-notification-overlay');
        if (existing) existing.remove();

        const overlay = document.createElement('div');
        overlay.className = 'ban-notification-overlay';

        const modal = document.createElement('div');
        modal.className = 'ban-notification-modal';

        let untilHtml = '';
        if (banData?.banned_until) {
            const dt = new Date(banData.banned_until);
            const locale = language === 'ru' ? 'ru-RU' : 'en-US';
            untilHtml = `${escapeHtml(config.texts.bannedUntil)} <strong>${escapeHtml(dt.toLocaleString(locale))}</strong>`;
        } else {
            untilHtml = `${escapeHtml(config.texts.bannedUntil)} <strong style="color:#ffdddd">${escapeHtml(config.texts.banPermanent)}</strong>`;
        }

        const reason = banData?.ban_reason ? `${escapeHtml(config.texts.banReasonLabel)} ${escapeHtml(banData.ban_reason)}` : '';

        modal.innerHTML = `
            <div style="display:flex; gap:14px; align-items:flex-start;">
                <div style="font-size:44px; line-height:44px;">🚫</div>
                <div style="flex:1;">
                    <div class="ban-notification-title">${escapeHtml(config.texts.banTitle)}</div>
                    <div class="ban-notification-box">
                        <div style="font-size:14px; line-height:1.5;">${untilHtml}</div>
                        ${reason ? `<div style="margin-top:10px; font-size:13px; opacity:0.95; line-height:1.45;">${reason}</div>` : ''}
                    </div>
                    <div style="display:flex; justify-content:flex-end; margin-top:14px;">
                        <button type="button" class="ban-notification-close">${escapeHtml(config.texts.banOk)}</button>
                    </div>
                </div>
            </div>
        `;

        overlay.appendChild(modal);
        document.body.appendChild(overlay);

        const close = () => overlay.remove();
        modal.querySelector('.ban-notification-close').addEventListener('click', close);
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) close();
        });
    };

    const appendMessage = (message) => {
        if (document.querySelector(`[data-chat-message-id="${message.id}"]`)) {
            return;
        }

        if (feed.querySelector('.global-chat-empty')) {
            feed.innerHTML = '';
        }

        const wrapper = document.createElement('div');
        wrapper.className = 'global-chat-message';
        wrapper.dataset.chatMessageId = message.id;

        const canModerate = config.isAdmin && Number(config.currentUserId) !== Number(message.author.id);
        const canReply = true;
        const quoteHtml = message.reply_to ? `
            <div class="global-chat-quote">
                <div><strong>${escapeHtml(config.texts.replyToLabel)}</strong> <a href="#chat-msg-${message.reply_to.id}" data-scroll-to="${message.reply_to.id}">@${escapeHtml(message.reply_to.author_username)}</a></div>
                <div>${escapeHtml(message.reply_to.content_preview)}</div>
            </div>
        ` : '';
        wrapper.innerHTML = `
            <a href="${message.author.profile_url}">
                <img class="global-chat-avatar" src="${message.author.avatar_url || config.defaultAvatar}" alt="${message.author.username}">
            </a>
            <div class="global-chat-body">
                <div class="global-chat-message-head">
                    <a class="global-chat-author" href="${message.author.profile_url}">${message.author.display_name || message.author.username}</a>
                    <a class="global-chat-time" href="${message.author.dm_url}">@${message.author.username}</a>
                    <span class="global-chat-time">${message.created_at}</span>
                </div>
                <div class="global-chat-content">${message.content_html.replace(/\n/g, '<br>')}</div>
                ${quoteHtml}
                <div class="global-chat-admin-actions">
                    ${canReply ? `<button type="button" data-action="reply">${config.texts.actionReply}</button>` : ''}
                    ${canModerate ? `
                        <button type="button" data-action="delete">${config.texts.actionDelete}</button>
                        <button type="button" data-action="ban">${config.texts.actionBan}</button>
                        <button type="button" data-action="unban">${config.texts.actionUnban}</button>
                    ` : ''}
                </div>
            </div>
        `;

        wrapper.id = `chat-msg-${message.id}`;

        const replyButton = wrapper.querySelector('[data-action="reply"]');
        if (replyButton) {
            replyButton.addEventListener('click', () => {
                replyToMessage = {
                    id: message.id,
                    author_username: message.author.username,
                    author_display_name: message.author.display_name || message.author.username,
                    content_preview: (message.content || '').slice(0, 160),
                };
                if (replyBox) {
                    replyBox.style.display = 'flex';
                    replyBox.innerHTML = `
                        <div>
                            <div class="reply-meta"><strong>${escapeHtml(config.texts.replyToLabel)}</strong> @${escapeHtml(replyToMessage.author_username)}</div>
                            <div class="reply-preview">${escapeHtml(replyToMessage.content_preview)}</div>
                        </div>
                        <button type="button" class="reply-cancel">${escapeHtml(config.texts.replyCancel)}</button>
                    `;
                    replyBox.querySelector('.reply-cancel').addEventListener('click', () => {
                        replyToMessage = null;
                        replyBox.style.display = 'none';
                        replyBox.innerHTML = '';
                    });
                }
                input?.focus();
            });
        }

        // Скролл к оригиналу из цитаты
        wrapper.querySelectorAll('[data-scroll-to]').forEach((a) => {
            a.addEventListener('click', (e) => {
                e.preventDefault();
                const targetId = a.getAttribute('data-scroll-to');
                const targetEl = document.getElementById(`chat-msg-${targetId}`);
                if (targetEl) {
                    targetEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            });
        });

        if (canModerate) {
            const deleteButton = wrapper.querySelector('[data-action="delete"]');
            const banButton = wrapper.querySelector('[data-action="ban"]');
            const unbanButton = wrapper.querySelector('[data-action="unban"]');

            deleteButton.addEventListener('click', async () => {
                if (!window.confirm(config.texts.confirmDelete)) {
                    return;
                }
                const response = await apiFetch(getDeleteUrl(message.id), { method: 'POST' });
                if (response.ok) {
                    wrapper.remove();
                    showNotice(config.texts.deleteSuccess, 'success');
                    return;
                }
                showNotice(config.texts.sendError, 'error');
            });

            banButton.addEventListener('click', async () => {
                if (!window.confirm(config.texts.confirmBan)) {
                    return;
                }
                const reason = window.prompt(config.texts.promptBanReason, '') || '';
                const durationHours = window.prompt(config.texts.promptBanDuration, '') || '';
                const body = new URLSearchParams({ reason, duration_hours: durationHours });
                const response = await apiFetch(getBanUrl(message.author.id), {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: body.toString(),
                });
                if (response.ok) {
                    showNotice(config.texts.banSuccess, 'success');
                    return;
                }
                showNotice(config.texts.sendError, 'error');
            });

            unbanButton.addEventListener('click', async () => {
                if (!window.confirm(config.texts.confirmUnban)) {
                    return;
                }
                const response = await apiFetch(getUnbanUrl(message.author.id), { method: 'POST' });
                if (response.ok) {
                    showNotice(config.texts.unbanSuccess, 'success');
                    return;
                }
                showNotice(config.texts.sendError, 'error');
            });
        }

        feed.appendChild(wrapper);
    };

    const removeMessageById = (messageId) => {
        const el = document.querySelector(`[data-chat-message-id="${messageId}"]`);
        if (el) el.remove();
    };

    const fetchMessages = async () => {
        try {
            const url = sinceCursor ? `${config.messagesUrl}?since=${encodeURIComponent(sinceCursor)}` : config.messagesUrl;
            const response = await apiFetch(url);
            if (!response.ok) {
                throw new Error(config.texts.loadError);
            }
            const data = await response.json();
            if (typeof data.since === 'string') {
                sinceCursor = data.since;
            }

            const events = Array.isArray(data.events) ? data.events : [];
            if (events.length === 0) {
                if (isInitialLoad && !feed.children.length) {
                    renderEmpty();
                }
                isInitialLoad = false;
                return;
            }

            events.forEach((evt) => {
                if (evt.type === 'deleted' && evt.message_id) {
                    removeMessageById(evt.message_id);
                    return;
                }
                if (evt.type === 'message' && evt.message) {
                    appendMessage(evt.message);
                }
            });

            if (isInitialLoad) {
                feed.scrollTop = feed.scrollHeight;
            }
            isInitialLoad = false;
        } catch (error) {
            showNotice(error.message || config.texts.loadError, 'error');
        }
    };

    if (form) {
        form.addEventListener('submit', async (event) => {
            if (config.currentUserId === 0) {
                return; // Let auth_modal.js handle the click/submit
            }
            event.preventDefault();
            const content = input.value.trim();
            if (!content) {
                return;
            }
            const body = new URLSearchParams({ content });
            if (replyToMessage?.id) {
                body.set('reply_to_id', String(replyToMessage.id));
            }
            const response = await apiFetch(config.sendUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: body.toString(),
            });

            if (response.status === 403) {
                let banPayload = null;
                try {
                    banPayload = await response.json();
                } catch (e) {
                    banPayload = null;
                }
                if (banPayload && (banPayload.ban_reason !== undefined || banPayload.banned_until !== undefined)) {
                    showBanOverlay(banPayload);
                } else {
                    showNotice(config.texts.banError, 'error');
                }
                return;
            }
            if (!response.ok) {
                showNotice(config.texts.sendError, 'error');
                return;
            }
            const data = await response.json();
            if (data.status === 'sent' && data.message) {
                appendMessage(data.message);
                input.value = '';
                feed.scrollTop = feed.scrollHeight;
                replyToMessage = null;
                if (replyBox) {
                    replyBox.style.display = 'none';
                    replyBox.innerHTML = '';
                }
            }
        });
    }

    fetchMessages();
    setInterval(fetchMessages, 2500);
});
