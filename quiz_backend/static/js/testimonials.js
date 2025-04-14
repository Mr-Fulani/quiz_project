'use strict';

console.log("testimonials.js loaded");

document.addEventListener('DOMContentLoaded', function () {
    console.log("testimonials.js DOMContentLoaded fired");

    const testimonialsItem = document.querySelectorAll('[data-testimonials-item]');
    const modalContainer = document.querySelector('[data-modal-container]');
    const modalCloseBtn = document.querySelector('[data-modal-close-btn]');
    const overlay = document.querySelector('[data-overlay]');
    const modalImg = document.querySelector('[data-modal-img]');
    const modalTitle = document.querySelector('[data-modal-title]');
    const modalText = document.querySelector('[data-modal-text]');
    const modalDate = document.querySelector('[data-modal-date]');
    const modalProfileLink = document.querySelector('[data-profile-link]');
    const isAuthenticated = document.body.dataset.authenticated === 'true'; // Проверка авторизации

    console.log("Found testimonials items:", testimonialsItem.length);
    if (testimonialsItem.length === 0) {
        console.error("No testimonials items found. Check if [data-testimonials-item] elements are present in the DOM.");
    }

    const testimonialsModalFunc = function () {
        if (modalContainer && overlay) {
            modalContainer.classList.toggle('active');
            overlay.classList.toggle('active');
            console.log("Modal toggled, active:", modalContainer.classList.contains('active'));
        } else {
            console.error("Modal container or overlay not found");
        }
    };

    for (let i = 0; i < testimonialsItem.length; i++) {
        testimonialsItem[i].addEventListener('click', function () {
            console.log("Card clicked:", i);
            const avatar = this.querySelector('[data-testimonials-avatar]').src;
            const alt = this.querySelector('[data-testimonials-avatar]').alt;
            const title = this.querySelector('[data-testimonials-title]').textContent;
            const text = this.querySelector('[data-testimonials-text]').innerHTML;
            const date = this.querySelector('[data-date-joined]') ? this.querySelector('[data-date-joined]').textContent : "14 June, 2023";
            const username = this.parentElement.getAttribute('data-username');

            console.log("Avatar:", avatar);
            console.log("Title:", title);
            console.log("Text:", text);
            console.log("Date:", date);
            console.log("Username:", username);

            if (modalImg) modalImg.src = avatar; else console.error("modalImg not found");
            if (modalImg) modalImg.alt = alt;
            if (modalTitle) modalTitle.textContent = title; else console.error("modalTitle not found");
            if (modalText) modalText.innerHTML = text; else console.error("modalText not found");
            if (modalDate) modalDate.textContent = "Member since: " + date; else console.error("modalDate not found");

            if (modalProfileLink && username) {
                if (isAuthenticated) {
                    modalProfileLink.href = `/users/user/${encodeURIComponent(username)}/`;
                    modalProfileLink.className = 'modal-profile-btn';
                    modalProfileLink.textContent = 'Перейти в профиль';
                    modalProfileLink.dataset.username = username;
                    console.log("Profile link set to:", modalProfileLink.href);
                } else {
                    modalProfileLink.href = '#';
                    modalProfileLink.className = 'open-login-modal';
                    modalProfileLink.textContent = 'Войдите, чтобы перейти в профиль';
                    modalProfileLink.dataset.returnUrl = `/users/user/${encodeURIComponent(username)}/`;
                    delete modalProfileLink.dataset.username;
                    console.log("Login link set with return URL:", modalProfileLink.dataset.returnUrl);
                }
            } else if (!modalProfileLink) {
                console.error("modalProfileLink not found");
            } else if (!username) {
                console.error("Username not found in data-username attribute");
            }

            testimonialsModalFunc();
        });
    }

    if (modalCloseBtn) modalCloseBtn.addEventListener('click', testimonialsModalFunc);
    if (overlay) overlay.addEventListener('click', testimonialsModalFunc);
});