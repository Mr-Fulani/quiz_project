document.addEventListener('DOMContentLoaded', function() {
    // Получение элементов DOM
    const loginModal = document.getElementById('login-modal');
    const registerModal = document.getElementById('register-modal');
    const forgotModal = document.getElementById('forgot-modal');
    
    // Открытие модальных окон
    const loginLink = document.getElementById('login-link');
    const forgotLink = document.getElementById('to-forgot');
    
    if (loginLink) {
        loginLink.addEventListener('click', function(e) {
            e.preventDefault();
            loginModal.style.display = 'flex';
        });
    }
    
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
        });
    }
    
    if (toLoginLink) {
        toLoginLink.addEventListener('click', function(e) {
            e.preventDefault();
            registerModal.style.display = 'none';
            loginModal.style.display = 'flex';
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
});