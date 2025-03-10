// quiz_backend/blog/static/blog/js/modal.js
document.addEventListener('DOMContentLoaded', function() {
    const profileTrigger = document.querySelector('[data-modal-trigger]');
    let modal = null;

    console.log('Modal script loaded. Looking for profile trigger...');
    if (!profileTrigger) {
        console.error('Profile trigger (data-modal-trigger) not found in DOM.');
        return;
    }

    function createModal() {
        modal = document.createElement('div');
        modal.className = 'modal';
        return modal;
    }

    function loadProfileModal() {
        if (!modal) {
            modal = createModal();
        }

        console.log('Fetching /profile/ content... URL: /profile/');
        fetch('/profile/', {
            method: 'GET',
            headers: {
                'X-Requested-With': 'XMLHttpRequest' // Указываем, что это AJAX-запрос
            }
        })
            .then(response => {
                if (!response.ok) {
                    console.error(`HTTP error! status: ${response.status} for URL: /profile/`);
                    console.log('Response text:', response.text()); // Попробуем получить текст ошибки
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                console.log('Response status: ' + response.status);
                return response.text();
            })
            .then(html => {
                console.log('Profile content fetched successfully. Length:', html.length);
                modal.innerHTML = `
                    <div class="modal-content">
                        <span class="close">×</span>
                        <div class="auth-container">${html}</div>
                    </div>
                `;
                document.body.appendChild(modal);

                // Обработчик закрытия
                const closeButton = modal.querySelector('.close');
                if (!closeButton) {
                    console.error('Close button (.close) not found in modal.');
                } else {
                    closeButton.addEventListener('click', function() {
                        document.body.removeChild(modal);
                        modal = null; // Сбрасываем ссылку на модал для повторного создания
                        console.log('Modal closed.');
                    });
                }

                // Переключение вкладок после загрузки
                const tabButtons = modal.querySelectorAll('.tab-button');
                const tabContents = modal.querySelectorAll('.tab-content');

                console.log(`Found ${tabButtons.length} tab buttons and ${tabContents.length} tab contents.`);
                if (tabButtons.length === 0 || tabContents.length === 0) {
                    console.error('Tab buttons or contents not found in modal.');
                }

                tabButtons.forEach(button => {
                    button.addEventListener('click', function() {
                        console.log(`Tab button clicked: ${this.dataset.tab}`);
                        tabButtons.forEach(btn => btn.classList.remove('active'));
                        tabContents.forEach(content => content.classList.remove('active'));

                        this.classList.add('active');
                        const tabId = this.dataset.tab;
                        const tabContent = document.getElementById(tabId);
                        if (!tabContent) {
                            console.error(`Tab content for ${tabId} not found.`);
                            return;
                        }
                        tabContent.classList.add('active');

                        const form = modal.querySelector(`#${tabId} form`);
                        if (form) {
                            let actionUrl;
                            switch (tabId) {
                                case 'login':
                                    actionUrl = '{% url "accounts:login" %}';
                                    break;
                                case 'register':
                                    actionUrl = '{% url "accounts:register" %}';
                                    break;
                                case 'forgot':
                                    actionUrl = '{% url "accounts:forgot" %}';
                                    break;
                                case 'profile':
                                    actionUrl = '{% url "accounts:profile" %}';
                                    break;
                                default:
                                    console.error(`Unknown tab ID: ${tabId}`);
                                    return;
                            }
                            form.action = actionUrl;
                            console.log(`Set form action to ${actionUrl} for tab ${tabId}.`);
                        }
                    });
                });

                // Обработка кликов по ссылкам
                const forgotLink = modal.querySelector('.forgot-link');
                const loginLink = modal.querySelector('.login-link');
                const registerLink = modal.querySelector('.register-link');

                if (forgotLink) {
                    forgotLink.addEventListener('click', function(e) {
                        e.preventDefault();
                        console.log('Forgot link clicked.');
                        const forgotButton = modal.querySelector('[data-tab="forgot"]');
                        if (forgotButton) forgotButton.click();
                        else console.error('Forgot tab button not found.');
                    });
                }

                if (loginLink) {
                    loginLink.addEventListener('click', function(e) {
                        e.preventDefault();
                        console.log('Login link clicked.');
                        const loginButton = modal.querySelector('[data-tab="login"]');
                        if (loginButton) loginButton.click();
                        else console.error('Login tab button not found.');
                    });
                }

                if (registerLink) {
                    registerLink.addEventListener('click', function(e) {
                        e.preventDefault();
                        console.log('Register link clicked.');
                        const registerButton = modal.querySelector('[data-tab="register"]');
                        if (registerButton) registerButton.click();
                        else console.error('Register tab button not found.');
                    });
                }
            })
            .catch(error => console.error('Error fetching profile:', error));
    }

    profileTrigger.addEventListener('click', function(e) {
        e.preventDefault();
        console.log('Profile trigger clicked. URL: ' + this.href + ', Target: ' + this.getAttribute('data-debug'));
        if (!modal || !document.body.contains(modal)) {
            loadProfileModal();
        }
    });

    window.addEventListener('click', function(event) {
        if (event.target === modal) {
            console.log('Modal background clicked, closing modal.');
            document.body.removeChild(modal);
            modal = null; // Сбрасываем ссылку на модал
        }
    });
});