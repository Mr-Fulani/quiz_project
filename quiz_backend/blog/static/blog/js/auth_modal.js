document.addEventListener('DOMContentLoaded', function() {
    console.log('Auth modal script loaded');
    // Получение элементов DOM
    const loginModal = document.getElementById('login-modal');
    const registerModal = document.getElementById('register-modal');
    const forgotModal = document.getElementById('forgot-modal');
    
    // Проверка URL-параметров для автоматического открытия модальных окон
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has('open_login')) {
        loginModal.style.display = 'flex';
    }
    if (urlParams.has('open_register')) {
        registerModal.style.display = 'flex';
    }
    if (urlParams.has('open_forgot')) {
        forgotModal.style.display = 'flex';
    }
    
    // Сохранение параметра next из URL в форму входа
    const nextParam = urlParams.get('next');
    if (nextParam && loginModal) {
        const loginForm = loginModal.querySelector('form');
        if (loginForm) {
            // Удаляем существующее поле next, если оно есть
            const existingNext = loginForm.querySelector('input[name="next"]');
            if (existingNext) {
                existingNext.remove();
            }
            
            // Создаем новое поле next
            const nextInput = document.createElement('input');
            nextInput.type = 'hidden';
            nextInput.name = 'next';
            nextInput.value = nextParam;
            loginForm.appendChild(nextInput);
        }
    }
    
    // Открытие модальных окон
    const loginLink = document.getElementById('login-link');
    console.log('Login link element:', loginLink);
    if (loginLink) {
        loginLink.addEventListener('click', function(e) {
            e.preventDefault();
            loginModal.style.display = 'flex';
        });
    }

    // Обработчик для ссылки входа в сайдбаре
    const sidebarLoginLink = document.getElementById('sidebar-login-link');
    if (sidebarLoginLink) {
        sidebarLoginLink.addEventListener('click', function(e) {
            e.preventDefault();
            loginModal.style.display = 'flex';
        });
    }
    
    // Обработчик для всех ссылок с классом open-login-modal
    const loginModalLinks = document.querySelectorAll('.open-login-modal');
    loginModalLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Получаем URL для возврата после входа
            const returnUrl = this.getAttribute('data-return-url');
            
            // Если есть URL для возврата, сохраняем его в скрытом поле формы
            if (returnUrl && loginModal) {
                const loginForm = loginModal.querySelector('form');
                if (loginForm) {
                    // Удаляем существующее поле next, если оно есть
                    const existingNext = loginForm.querySelector('input[name="next"]');
                    if (existingNext) {
                        existingNext.remove();
                    }
                    
                    // Создаем новое поле next
                    const nextInput = document.createElement('input');
                    nextInput.type = 'hidden';
                    nextInput.name = 'next';
                    nextInput.value = returnUrl;
                    loginForm.appendChild(nextInput);
                }
            }
            
            // Открываем модальное окно входа
            loginModal.style.display = 'flex';
        });
    });
    
    // Закрытие модальных окон
    const closeBtns = document.querySelectorAll('.close-btn');
    closeBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            loginModal.style.display = 'none';
            registerModal.style.display = 'none';
            forgotModal.style.display = 'none';
        });
    });
    
    // Закрытие модальных окон при клике вне их области
    window.addEventListener('click', function(e) {
        if (e.target === loginModal) {
            loginModal.style.display = 'none';
        }
        if (e.target === registerModal) {
            registerModal.style.display = 'none';
        }
        if (e.target === forgotModal) {
            forgotModal.style.display = 'none';
        }
    });
    
    // Переключение между формами
    const toRegisterLink = document.getElementById('to-register');
    const toLoginLink = document.getElementById('to-login');
    const toForgotLink = document.getElementById('to-forgot');
    const backToLoginLink = document.getElementById('back-to-login');
    
    if (toRegisterLink) {
        toRegisterLink.addEventListener('click', function(e) {
            e.preventDefault();
            loginModal.style.display = 'none';
            registerModal.style.display = 'flex';
            
            // Передаем параметр next из формы входа в форму регистрации
            const loginForm = loginModal.querySelector('form');
            const registerForm = registerModal.querySelector('form');
            if (loginForm && registerForm) {
                const nextInput = loginForm.querySelector('input[name="next"]');
                if (nextInput) {
                    // Удаляем существующее поле next в форме регистрации, если оно есть
                    const existingNext = registerForm.querySelector('input[name="next"]');
                    if (existingNext) {
                        existingNext.remove();
                    }
                    
                    // Создаем новое поле next в форме регистрации
                    const newNextInput = document.createElement('input');
                    newNextInput.type = 'hidden';
                    newNextInput.name = 'next';
                    newNextInput.value = nextInput.value;
                    registerForm.appendChild(newNextInput);
                }
            }
        });
    }
    
    if (toLoginLink) {
        toLoginLink.addEventListener('click', function(e) {
            e.preventDefault();
            registerModal.style.display = 'none';
            loginModal.style.display = 'flex';
            
            // Передаем параметр next из формы регистрации в форму входа
            const registerForm = registerModal.querySelector('form');
            const loginForm = loginModal.querySelector('form');
            if (registerForm && loginForm) {
                const nextInput = registerForm.querySelector('input[name="next"]');
                if (nextInput) {
                    // Удаляем существующее поле next в форме входа, если оно есть
                    const existingNext = loginForm.querySelector('input[name="next"]');
                    if (existingNext) {
                        existingNext.remove();
                    }
                    
                    // Создаем новое поле next в форме входа
                    const newNextInput = document.createElement('input');
                    newNextInput.type = 'hidden';
                    newNextInput.name = 'next';
                    newNextInput.value = nextInput.value;
                    loginForm.appendChild(newNextInput);
                }
            }
        });
    }
    
    if (toForgotLink) {
        toForgotLink.addEventListener('click', function(e) {
            e.preventDefault();
            loginModal.style.display = 'none';
            forgotModal.style.display = 'flex';
        });
    }
    
    if (backToLoginLink) {
        backToLoginLink.addEventListener('click', function(e) {
            e.preventDefault();
            forgotModal.style.display = 'none';
            loginModal.style.display = 'flex';
        });
    }
    
    // Обработка клавиши Escape для закрытия модальных окон
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            loginModal.style.display = 'none';
            registerModal.style.display = 'none';
            forgotModal.style.display = 'none';
        }
    });
});