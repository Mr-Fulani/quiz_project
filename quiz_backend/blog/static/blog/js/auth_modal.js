document.addEventListener('DOMContentLoaded', function() {
    console.log('Auth modal script loaded');

    // Получение элементов DOM
    const loginModal = document.getElementById('login-modal');
    const registerModal = document.getElementById('register-modal');
    const forgotModal = document.getElementById('forgot-modal');

    // Проверяем существование модальных окон (для авторизованных пользователей они могут отсутствовать)
    if (!loginModal) {
        console.log('Login modal not found - user may be authenticated');
        return;
    }

    // Отправка формы логина через AJAX
    const loginForm = loginModal.querySelector('.login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', function(e) {
            e.preventDefault(); // Предотвращаем стандартную отправку формы

            const formData = new FormData(loginForm);
            const errorMessage = loginModal.querySelector('.error-message');

            fetch(loginForm.action, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': formData.get('csrfmiddlewaretoken'),
                },
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(data => {
                        throw new Error(data.error || 'Login failed');
                    });
                }
                return response.json();
            })
            .then(data => {
                // Успешный вход
                const nextUrl = data.next || '/';
                window.location.href = nextUrl; // Перенаправление
            })
            .catch(error => {
                // Ошибка (например, неверный пароль)
                errorMessage.textContent = error.message || 'An error occurred';
            });
        });
    }

    /**
     * Проверяет URL-параметры и автоматически открывает соответствующее модальное окно,
     * если в URL есть 'open_login', 'open_register' или 'open_forgot'.
     */
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has('open_login')) {
        loginModal.classList.add('active');
    }
    if (urlParams.has('open_register')) {
        registerModal.classList.add('active');
    }
    if (urlParams.has('open_forgot')) {
        forgotModal.classList.add('active');
    }

    /**
     * Добавляет скрытое поле 'next' в форму входа, если в URL есть параметр 'next'.
     * Это позволяет перенаправить пользователя на нужную страницу после входа.
     */
    const nextParam = urlParams.get('next');
    if (nextParam && loginModal) {
        const loginForm = loginModal.querySelector('form');
        if (loginForm) {
            const existingNext = loginForm.querySelector('input[name="next"]');
            if (existingNext) {
                existingNext.remove();
            }
            const nextInput = document.createElement('input');
            nextInput.type = 'hidden';
            nextInput.name = 'next';
            nextInput.value = nextParam;
            loginForm.appendChild(nextInput);
        }
    }

    /**
     * Открывает модальное окно входа по клику на статическую ссылку с id 'login-link'.
     */
    const loginLink = document.getElementById('login-link');
    console.log('Login link element:', loginLink);
    if (loginLink) {
        loginLink.addEventListener('click', function(e) {
            e.preventDefault();
            loginModal.classList.add('active');
        });
    }

    /**
     * Открывает модальное окно входа по клику на ссылку в сайдбаре с id 'sidebar-login-link'.
     */
    const sidebarLoginLink = document.getElementById('sidebar-login-link');
    if (sidebarLoginLink) {
        sidebarLoginLink.addEventListener('click', function(e) {
            e.preventDefault();
            loginModal.classList.add('active');
        });
    }

    /**
     * Обрабатывает клики по элементам с классом 'open-login-modal' через делегирование событий.
     * Работает как для статичных, так и для динамически добавленных элементов.
     * Открывает модальное окно входа и добавляет поле 'next' с URL из 'data-return-url'.
     */
    document.addEventListener('click', function(e) {
        const target = e.target.closest('.open-login-modal');
        if (target) {
            e.preventDefault();
            const returnUrl = target.getAttribute('data-return-url');
            if (returnUrl && loginModal) {
                const loginForm = loginModal.querySelector('form');
                if (loginForm) {
                    const existingNext = loginForm.querySelector('input[name="next"]');
                    if (existingNext) existingNext.remove();
                    const nextInput = document.createElement('input');
                    nextInput.type = 'hidden';
                    nextInput.name = 'next';
                    nextInput.value = returnUrl;
                    loginForm.appendChild(nextInput);
                }
            }
            loginModal.classList.add('active');
            console.log("Login modal opened, return URL:", returnUrl);
        }
    });

    /**
     * Добавляет обработчики закрытия модальных окон для всех кнопок с классом 'close-btn'.
     */
    const closeBtns = document.querySelectorAll('.close-btn');
    closeBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            loginModal.classList.remove('active');
            registerModal.classList.remove('active');
            forgotModal.classList.remove('active');
        });
    });

    /**
     * Закрывает модальные окна при клике вне их области (на оверлей).
     */
    window.addEventListener('click', function(e) {
        if (e.target === loginModal) {
            loginModal.classList.remove('active');
        }
        if (e.target === registerModal) {
            registerModal.classList.remove('active');
        }
        if (e.target === forgotModal) {
            forgotModal.classList.remove('active');
        }
    });

    // Переключение между формами
    const toRegisterLink = document.getElementById('to-register');
    const toLoginLink = document.getElementById('to-login');
    const toForgotLink = document.getElementById('to-forgot');
    const backToLoginLink = document.getElementById('back-to-login');

    /**
     * Переключает с формы входа на форму регистрации и переносит поле 'next', если оно есть.
     */
    if (toRegisterLink) {
        toRegisterLink.addEventListener('click', function(e) {
            e.preventDefault();
            loginModal.classList.remove('active');
            registerModal.classList.add('active');
            const loginForm = loginModal.querySelector('form');
            const registerForm = registerModal.querySelector('form');
            if (loginForm && registerForm) {
                const nextInput = loginForm.querySelector('input[name="next"]');
                if (nextInput) {
                    const existingNext = registerForm.querySelector('input[name="next"]');
                    if (existingNext) existingNext.remove();
                    const newNextInput = document.createElement('input');
                    newNextInput.type = 'hidden';
                    newNextInput.name = 'next';
                    newNextInput.value = nextInput.value;
                    registerForm.appendChild(newNextInput);
                }
            }
        });
    }

    /**
     * Переключает с формы регистрации на форму входа и переносит поле 'next', если оно есть.
     */
    if (toLoginLink) {
        toLoginLink.addEventListener('click', function(e) {
            e.preventDefault();
            registerModal.classList.remove('active');
            loginModal.classList.add('active');
            const registerForm = registerModal.querySelector('form');
            const loginForm = loginModal.querySelector('form');
            if (registerForm && loginForm) {
                const nextInput = registerForm.querySelector('input[name="next"]');
                if (nextInput) {
                    const existingNext = loginForm.querySelector('input[name="next"]');
                    if (existingNext) existingNext.remove();
                    const newNextInput = document.createElement('input');
                    newNextInput.type = 'hidden';
                    newNextInput.name = 'next';
                    newNextInput.value = nextInput.value;
                    loginForm.appendChild(newNextInput);
                }
            }
        });
    }

    /**
     * Переключает с формы входа на форму восстановления пароля.
     */
    if (toForgotLink) {
        toForgotLink.addEventListener('click', function(e) {
            e.preventDefault();
            loginModal.classList.remove('active');
            forgotModal.classList.add('active');
        });
    }

    /**
     * Возвращает с формы восстановления пароля на форму входа.
     */
    if (backToLoginLink) {
        backToLoginLink.addEventListener('click', function(e) {
            e.preventDefault();
            forgotModal.classList.remove('active');
            loginModal.classList.add('active');
        });
    }

    /**
     * Закрывает все модальные окна при нажатии клавиши Escape.
     */
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            loginModal.classList.remove('active');
            registerModal.classList.remove('active');
            forgotModal.classList.remove('active');
        }
    });
});