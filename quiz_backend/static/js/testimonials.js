/**
 * testimonials.js
 * Script for managing testimonials on the page
 *
 * Functionality:
 * - Opening/closing modal windows
 * - Submitting new testimonials
 * - Viewing existing testimonials
 * - Handling user avatars
 */

'use strict';

console.log("testimonials.js loaded");

// Localization strings - these will be set from Django template
window.testimonialsTranslations = window.testimonialsTranslations || {
    'viewProfile': 'View Profile',
    'loginToViewProfile': 'Login to view profile',
    'profileUnavailable': 'Profile unavailable',
    'modalClosed': 'Modal closed',
    'modalOpened': 'Modal opened',
    'userNotAuthenticated': 'User not authenticated, preventing modal open',
    'addTestimonialModalOpened': 'Add testimonial modal opened',
    'addTestimonialButtonNotFound': 'Add testimonial button not found',
    'addTestimonialModalNotFound': 'Add testimonial modal not found',
    'modalNotFoundForClosing': 'Modal not found for closing',
    'thankYouTestimonialAdded': 'Thank you! Your testimonial has been successfully added.',
    'errorSubmittingTestimonial': 'An error occurred while submitting the testimonial. Please try again.',
    'addTestimonialButtonClicked': 'Add testimonial button clicked, isAuthenticated:'
};

document.addEventListener('DOMContentLoaded', function () {
    console.log("testimonials.js DOMContentLoaded fired");

    // Handlers for testimonial viewing modal
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

    // Function for testimonial viewing modal
    const testimonialsModalFunc = function () {
        if (modalContainer && overlay) {
            modalContainer.classList.toggle('active');
            overlay.classList.toggle('active');
            console.log(window.testimonialsTranslations.modalClosed + ", active:", modalContainer.classList.contains('active'));
        }
    }

    // Click handler for testimonials
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

            // Extended debugging for username
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

            // Check for modal elements
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
                        const profileUrl = `/accounts/user/${encodeURIComponent(username)}/`;
                        modalProfileLink.href = profileUrl;
                        modalProfileLink.className = 'modal-profile-btn';
                        modalProfileLink.textContent = window.testimonialsTranslations.viewProfile;
                        modalProfileLink.dataset.username = username;
                        console.log("✓ Profile URL set to:", profileUrl);
                        console.log("✓ Link href after setting:", modalProfileLink.href);
                    } else {
                        modalProfileLink.href = '#';
                        modalProfileLink.className = 'open-login-modal';
                        modalProfileLink.textContent = window.testimonialsTranslations.loginToViewProfile;
                        modalProfileLink.dataset.returnUrl = `/accounts/user/${encodeURIComponent(username)}/`;
                        delete modalProfileLink.dataset.username;
                        console.log("✓ User not authenticated, login modal required");
                    }
                } else {
                    console.error("✗ Username is empty or undefined");
                    modalProfileLink.href = '#';
                    modalProfileLink.textContent = window.testimonialsTranslations.profileUnavailable;
                }
            } else {
                console.error("✗ Modal profile link element not found");
            }

            testimonialsModalFunc();
        });
    });

    // Modal close handlers setup
    const setupModalCloseHandlers = function() {
        // For all modal windows
        document.querySelectorAll('.modal-container').forEach(modal => {
            const overlay = modal.querySelector('.overlay');
            const closeBtn = modal.querySelector('.modal-close-btn');

            if (overlay) {
                overlay.addEventListener('click', function() {
                    modal.classList.remove('active');
                    this.classList.remove('active');
                    console.log(window.testimonialsTranslations.modalClosed + " by overlay click");
                });
            }

            if (closeBtn) {
                closeBtn.addEventListener('click', function() {
                    modal.classList.remove('active');
                    if (overlay) overlay.classList.remove('active');
                    console.log(window.testimonialsTranslations.modalClosed + " by button click");
                });
            }
        });
    };

    setupModalCloseHandlers();

    // Handlers for add testimonial modal
    const addTestimonialModal = document.getElementById('add-testimonial-modal');
    const testimonialForm = document.getElementById('testimonial-form');

    /**
     * Closes the specified modal by removing the active class
     * @param {HTMLElement} modal - Modal window to close
     */
    const closeModal = function(modal) {
        if (modal) {
            modal.classList.remove('active');
            const modalOverlay = modal.querySelector('.overlay');
            if (modalOverlay) {
                modalOverlay.classList.remove('active');
            }
            console.log(window.testimonialsTranslations.modalClosed + ':', modal.id || 'unknown');
        } else {
            console.error(window.testimonialsTranslations.modalNotFoundForClosing);
        }
    };

    /**
     * Opens the add testimonial modal by adding the active class
     * Checks user authentication and opens modal only for authenticated users
     * @param {Event} e - Click event
     */
    const openAddTestimonialModal = function(e) {
        console.log(window.testimonialsTranslations.addTestimonialButtonClicked, isAuthenticated);
        if (!isAuthenticated) {
            e.preventDefault();
            console.log(window.testimonialsTranslations.userNotAuthenticated);
            return;
        }

        if (addTestimonialModal) {
            addTestimonialModal.classList.add('active');
            const addTestimonialOverlay = addTestimonialModal.querySelector('.overlay');
            if (addTestimonialOverlay) {
                addTestimonialOverlay.classList.add('active');
            }
            console.log(window.testimonialsTranslations.addTestimonialModalOpened);
        } else {
            console.error(window.testimonialsTranslations.addTestimonialModalNotFound);
        }
    };

    // Bind handler to add testimonial button
    const addButton = document.querySelector('.add-testimonial-button .btn');
    if (addButton) {
        addButton.addEventListener('click', openAddTestimonialModal);
    } else {
        console.error(window.testimonialsTranslations.addTestimonialButtonNotFound);
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
                    // Create and show notification
                    const notification = document.createElement('div');
                    notification.className = 'message-notification success';
                    notification.textContent = window.testimonialsTranslations.thankYouTestimonialAdded;
                    document.body.appendChild(notification);

                    // Close modal
                    closeModal(addTestimonialModal);

                    // Remove notification after 3 seconds
                    setTimeout(() => {
                        notification.remove();
                        location.reload(); // Reload page to display new testimonial
                    }, 3000);
                } else {
                    alert(window.testimonialsTranslations.errorSubmittingTestimonial);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert(window.testimonialsTranslations.errorSubmittingTestimonial);
            });
        });
    }
});