/**
 * testimonials.js
 * Скрипт управления отзывами на странице
 * 
 * Функционал:
 * - Открытие/закрытие модальных окон
 * - Отправка новых отзывов
 * - Просмотр существующих отзывов
 * - Обработка аватарок пользователей
 */

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

    // В функции обработки клика на отзыв (testimonials.js)
    testimonialsItem.forEach(item => {
        item.addEventListener('click', function () {
            console.log("=== TESTIMONIAL CLICKED ===");
            console.log("Clicked item:", this);

            const avatarImg = this.querySelector('[data-testimonials-avatar]');
            const defaultAvatarUrl = window.defaultAvatarUrl || '/static/images/default_avatar.png';

            const avatar = avatarImg && avatarImg.src ? avatarImg.src : defaultAvatarUrl;
            const title = this.querySelector('[data-testimonials-title]').textContent;
            const text = this.querySelector('[data-testimonials-text]').innerHTML;
            const date = this.querySelector('[data-date-joined]')?.textContent;

            // Расширенная отладка для username
            const testimonialsItemElement = this.closest('.testimonials-item');
            console.log("Testimonials item element:", testimonialsItemElement);
            console.log("All datasets on testimonials item:", testimonialsItemElement?.dataset);
            const username = testimonialsItemElement?.dataset.username;

            console.log("=== EXTRACTED DATA ===");
            console.log("Avatar:", avatar);
            console.log("Title:", title);
            console.log("Text:", text);
            console.log("Date:", date);
            console.log("Username:", username);
            console.log("Is authenticated:", isAuthenticated);

            // Проверяем наличие элементов модального окна
            console.log("=== MODAL ELEMENTS ===");
            console.log("modalImg:", modalImg);
            console.log("modalTitle:", modalTitle);
            console.log("modalText:", modalText);
            console.log("modalDate:", modalDate);
            console.log("modalProfileLink:", modalProfileLink);

            if (modalImg) modalImg.src = avatar;
            modalImg.onerror = function() {
                this.src = defaultAvatarUrl;
            };
            if (modalTitle) modalTitle.textContent = title;
            if (modalText) modalText.innerHTML = text;
            if (modalDate && date) modalDate.textContent = date;

            if (modalProfileLink) {
                console.log("=== SETTING PROFILE LINK ===");
                if (username) {
                    if (isAuthenticated) {
                        const profileUrl = `/users/user/${encodeURIComponent(username)}/`;
                        modalProfileLink.href = profileUrl;
                        modalProfileLink.className = 'modal-profile-btn';
                        modalProfileLink.textContent = 'Перейти в профиль';
                        modalProfileLink.dataset.username = username;
                        console.log("✓ Profile URL set to:", profileUrl);
                        console.log("✓ Link href after setting:", modalProfileLink.href);
                    } else {
                        modalProfileLink.href = '#';
                        modalProfileLink.className = 'open-login-modal';
                        modalProfileLink.textContent = 'Войдите, чтобы перейти в профиль';
                        modalProfileLink.dataset.returnUrl = `/users/user/${encodeURIComponent(username)}/`;
                        delete modalProfileLink.dataset.username;
                        console.log("✓ User not authenticated, login modal required");
                    }
                } else {
                    console.error("✗ Username is empty or undefined");
                    modalProfileLink.href = '#';
                    modalProfileLink.textContent = 'Профиль недоступен';
                }
            } else {
                console.error("✗ Modal profile link element not found");
            }

            testimonialsModalFunc();
        });
    });

    // Обработчики закрытия модальных окон
    const setupModalCloseHandlers = function() {
        // Для всех модальных окон
        document.querySelectorAll('.modal-container').forEach(modal => {
            const overlay = modal.querySelector('.overlay');
            const closeBtn = modal.querySelector('.modal-close-btn');

            if (overlay) {
                overlay.addEventListener('click', function() {
                    modal.classList.remove('active');
                    this.classList.remove('active');
                    console.log("Modal closed by overlay click");
                });
            }

            if (closeBtn) {
                closeBtn.addEventListener('click', function() {
                    modal.classList.remove('active');
                    if (overlay) overlay.classList.remove('active');
                    console.log("Modal closed by button click");
                });
            }
        });
    };

    setupModalCloseHandlers();

    // Обработчики для модального окна добавления отзыва
    const addTestimonialModal = document.getElementById('add-testimonial-modal');
    const testimonialForm = document.getElementById('testimonial-form');

    /**
     * Закрывает указанное модальное окно, убирая класс active
     * @param {HTMLElement} modal - Модальное окно для закрытия
     */
    const closeModal = function(modal) {
        if (modal) {
            modal.classList.remove('active');
            const modalOverlay = modal.querySelector('.overlay');
            if (modalOverlay) {
                modalOverlay.classList.remove('active');
            }
            console.log('Modal closed:', modal.id || 'unknown');
        } else {
            console.error('Modal not found for closing');
        }
    };

    /**
     * Открывает модальное окно для добавления отзыва, добавляя класс active
     * Проверяет авторизацию пользователя и открывает модальное окно только для авторизованных
     * @param {Event} e - Событие клика
     */
    const openAddTestimonialModal = function(e) {
        console.log('Add testimonial button clicked, isAuthenticated:', isAuthenticated);
        if (!isAuthenticated) {
            e.preventDefault();
            console.log('User not authenticated, preventing modal open');
            return;
        }

        if (addTestimonialModal) {
            addTestimonialModal.classList.add('active');
            const addTestimonialOverlay = addTestimonialModal.querySelector('.overlay');
            if (addTestimonialOverlay) {
                addTestimonialOverlay.classList.add('active');
            }
            console.log('Add testimonial modal opened');
        } else {
            console.error('Add testimonial modal not found');
        }
    };

    // Привязываем обработчик к кнопке добавления отзыва
    const addButton = document.querySelector('.add-testimonial-button .btn');
    if (addButton) {
        addButton.addEventListener('click', openAddTestimonialModal);
    } else {
        console.error('Add testimonial button not found');
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
                    // Создаем и показываем уведомление
                    const notification = document.createElement('div');
                    notification.className = 'message-notification success';
                    notification.textContent = 'Спасибо! Ваш отзыв успешно добавлен.';
                    document.body.appendChild(notification);

                    // Закрываем модальное окно
                    closeModal(addTestimonialModal);

                    // Удаляем уведомление через 3 секунды
                    setTimeout(() => {
                        notification.remove();
                        location.reload(); // Перезагружаем страницу для отображения нового отзыва
                    }, 3000);
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