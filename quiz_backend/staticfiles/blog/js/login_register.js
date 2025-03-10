// quiz_backend/blog/static/blog/js/login_register.js
document.addEventListener('DOMContentLoaded', function() {
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabContents = document.querySelectorAll('.tab-content');

    tabButtons.forEach(button => {
        button.addEventListener('click', function() {
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabContents.forEach(content => content.classList.remove('active'));

            this.classList.add('active');
            document.getElementById(this.dataset.tab).classList.add('active');

            const form = document.querySelector(`#${this.dataset.tab} form`);
            if (form) {
                let actionUrl;
                switch (this.dataset.tab) {
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
                }
                form.action = actionUrl;
            }
        });
    });

    // Обработка кликов по ссылкам
    document.querySelector('.forgot-link')?.addEventListener('click', function(e) {
        e.preventDefault();
        document.querySelector('[data-tab="forgot"]').click();
    });

    document.querySelector('.login-link')?.addEventListener('click', function(e) {
        e.preventDefault();
        document.querySelector('[data-tab="login"]').click();
    });

    document.querySelector('.register-link')?.addEventListener('click', function(e) {
        e.preventDefault();
        document.querySelector('[data-tab="register"]').click();
    });
});