'use strict';

console.log("testimonials.js loaded");

document.addEventListener('DOMContentLoaded', function () {
    console.log("testimonials.js DOMContentLoaded fired");

    // Обработчики для модального окна просмотра отзывов
    const testimonialsItem = document.querySelectorAll('[data-testimonials-item]');
    const modalContainer = document.querySelector('[data-modal-container]');
    const modalCloseBtn = document.querySelector('[data-modal-close-btn]');
    const overlay = document.querySelector('[data-overlay]');
    const modalImg = document.querySelector('[data-modal-img]');
    const modalTitle = document.querySelector('[data-modal-title]');
    const modalText = document.querySelector('[data-modal-text]');
    const modalDate = document.querySelector('[data-modal-date]');
    const modalProfileLink = document.querySelector('[data-profile-link]');
    const isAuthenticated = document.body.dataset.authenticated === 'true';

    console.log("Found testimonials items:", testimonialsItem.length);
    
    // Функция для модального окна просмотра отзывов
    const testimonialsModalFunc = function () {
        if (modalContainer && overlay) {
            modalContainer.classList.toggle('active');
            overlay.classList.toggle('active');
            console.log("Modal toggled, active:", modalContainer.classList.contains('active'));
        }
    }

    // Обработчики для просмотра отзывов
    testimonialsItem.forEach(item => {
        item.addEventListener('click', function () {
            console.log("Testimonial clicked");
            const avatar = this.querySelector('[data-testimonials-avatar]').src;
            const title = this.querySelector('[data-testimonials-title]').textContent;
            const text = this.querySelector('[data-testimonials-text]').innerHTML;
            const date = this.querySelector('[data-date-joined]')?.textContent;
            const username = this.closest('.testimonials-item').dataset.username;

            console.log("Avatar:", avatar);
            console.log("Title:", title);
            console.log("Text:", text);
            console.log("Date:", date);
            console.log("Username:", username);

            if (modalImg) modalImg.src = avatar;
            if (modalTitle) modalTitle.textContent = title;
            if (modalText) modalText.innerHTML = text;
            if (modalDate && date) modalDate.textContent = date;

            if (modalProfileLink && username) {
                if (isAuthenticated) {
                    modalProfileLink.href = `/users/user/${encodeURIComponent(username)}/`;
                    modalProfileLink.className = 'modal-profile-btn';
                    modalProfileLink.textContent = 'Перейти в профиль';
                    modalProfileLink.dataset.username = username;
                } else {
                    modalProfileLink.href = '#';
                    modalProfileLink.className = 'open-login-modal';
                    modalProfileLink.textContent = 'Войдите, чтобы перейти в профиль';
                    modalProfileLink.dataset.returnUrl = `/users/user/${encodeURIComponent(username)}/`;
                    delete modalProfileLink.dataset.username;
                }
            }

            testimonialsModalFunc();
        });
    });

    if (modalCloseBtn) {
        modalCloseBtn.addEventListener('click', testimonialsModalFunc);
    }
    if (overlay) {
        overlay.addEventListener('click', testimonialsModalFunc);
    }

    // Обработчики для модального окна добавления отзыва
    const addTestimonialBtn = document.querySelector('.add-testimonial-button .btn');
    const addTestimonialModal = document.getElementById('add-testimonial-modal');
    const testimonialForm = document.getElementById('testimonial-form');

    if (addTestimonialBtn && addTestimonialModal) {
        addTestimonialBtn.addEventListener('click', function() {
            addTestimonialModal.classList.add('active');
            const addTestimonialOverlay = addTestimonialModal.querySelector('.overlay');
            if (addTestimonialOverlay) {
                addTestimonialOverlay.classList.add('active');
            }
        });
    }

    const closeAddTestimonialModal = function() {
        if (addTestimonialModal) {
            addTestimonialModal.classList.remove('active');
            const addTestimonialOverlay = addTestimonialModal.querySelector('.overlay');
            if (addTestimonialOverlay) {
                addTestimonialOverlay.classList.remove('active');
            }
        }
    };

    if (addTestimonialModal) {
        const closeBtn = addTestimonialModal.querySelector('.modal-close-btn');
        const modalOverlay = addTestimonialModal.querySelector('.overlay');
        
        if (closeBtn) {
            closeBtn.addEventListener('click', closeAddTestimonialModal);
        }
        if (modalOverlay) {
            modalOverlay.addEventListener('click', closeAddTestimonialModal);
        }
    }

    if (testimonialForm) {
        testimonialForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const formData = new FormData(this);
            
            fetch(window.location.href, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                },
                credentials: 'same-origin'
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    closeAddTestimonialModal();
                    location.reload();
                } else {
                    alert('Произошла ошибка при отправке отзыва. Пожалуйста, попробуйте снова.');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Произошла ошибка при отправке отзыва. Пожалуйста, попробуйте снова.');
            });
        });
    }
});