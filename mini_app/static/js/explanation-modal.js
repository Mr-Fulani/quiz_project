/**
 * @fileoverview Explanation modal component for quiz polls
 * 
 * This module handles the creation and management of a modal window 
 * that displays explanations for quiz questions when a user selects
 * the "Не знаю, но хочу узнать" option.
 */

/**
 * ExplanationModal - Creates and manages the explanation modal
 */
class ExplanationModal {
  /**
   * @typedef {Object} ModalOptions
   * @property {string} [closeButtonText='✕'] - Text for the close button
   * @property {string} [modalClass='explanation-modal'] - CSS class for the modal
   * @property {string} [overlayClass='modal-overlay'] - CSS class for the overlay
   * @property {string} [contentClass='modal-content'] - CSS class for the content container
   * @property {string} [closeButtonClass='modal-close'] - CSS class for the close button
   * @property {boolean} [closeOnOutsideClick=true] - Whether to close on outside click (desktop only)
   */

  /**
   * @type {HTMLElement|null} - Modal container element
   * @private
   */
  #modalElement = null;

  /**
   * @type {HTMLElement|null} - Modal overlay element
   * @private
   */
  #overlayElement = null;

  /**
   * @type {HTMLElement|null} - Modal content element
   * @private
   */
  #contentElement = null;

  /**
   * @type {HTMLElement|null} - Close button element
   * @private
   */
  #closeButton = null;

  /**
   * @type {ModalOptions} - Modal configuration options
   * @private
   */
  #options;

  /**
   * @type {boolean} - Is the modal currently visible
   * @private
   */
  #isVisible = false;

  /**
   * @type {boolean} - Is the current device a mobile device
   * @private 
   */
  #isMobile = false;

  /**
   * Creates a new explanation modal instance
   * @param {ModalOptions} [options] - Configuration options
   */
  constructor(options = {}) {
    this.#options = {
      closeButtonText: '✕',
      modalClass: 'explanation-modal',
      overlayClass: 'modal-overlay',
      contentClass: 'modal-content',
      closeButtonClass: 'modal-close',
      closeOnOutsideClick: true,
      ...options
    };
    
    // Check if mobile
    this.#isMobile = this.#checkIfMobile();
    
    // Create modal elements
    this.#createModalElements();
    
    // Add event listeners
    this.#addEventListeners();
  }

  /**
   * Checks if the current device is a mobile device
   * @returns {boolean} - True if mobile device
   * @private
   */
  #checkIfMobile() {
    return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
  }

  /**
   * Creates the modal HTML elements
   * @private
   */
  #createModalElements() {
    // Create modal container
    this.#modalElement = document.createElement('div');
    this.#modalElement.className = this.#options.modalClass;
    this.#modalElement.style.display = 'none';
    
    // Create overlay
    this.#overlayElement = document.createElement('div');
    this.#overlayElement.className = this.#options.overlayClass;
    
    // Create content container
    this.#contentElement = document.createElement('div');
    this.#contentElement.className = this.#options.contentClass;
    
    // Create close button (always visible on mobile)
    this.#closeButton = document.createElement('button');
    this.#closeButton.className = this.#options.closeButtonClass;
    this.#closeButton.innerHTML = this.#options.closeButtonText;
    
    // Assemble modal structure
    this.#contentElement.appendChild(this.#closeButton);
    this.#modalElement.appendChild(this.#overlayElement);
    this.#modalElement.appendChild(this.#contentElement);
    
    // Add to document
    document.body.appendChild(this.#modalElement);
  }

  /**
   * Adds event listeners to modal elements
   * @private
   */
  #addEventListeners() {
    // Close button click
    this.#closeButton.addEventListener('click', () => {
      this.hide();
    });
    
    // Outside click (desktop only)
    if (this.#options.closeOnOutsideClick && !this.#isMobile) {
      this.#overlayElement.addEventListener('click', (e) => {
        if (e.target === this.#overlayElement) {
          this.hide();
        }
      });
    }
    
    // Handle escape key
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && this.#isVisible) {
        this.hide();
      }
    });
  }

  /**
   * Shows the modal with the provided explanation text
   * @param {string} explanationText - The explanation text to display
   * @public
   */
  show(explanationText) {
    if (!explanationText) {
      console.warn('No explanation text provided to modal');
      return;
    }
    
    // Set content
    const contentContainer = document.createElement('div');
    contentContainer.className = 'explanation-text';
    contentContainer.innerHTML = explanationText;
    
    // Clear any existing content except close button
    while (this.#contentElement.childNodes.length > 1) {
      this.#contentElement.removeChild(this.#contentElement.lastChild);
    }
    
    // Add new content
    this.#contentElement.appendChild(contentContainer);
    
    // Show modal
    this.#modalElement.style.display = 'block';
    this.#isVisible = true;
    
    // Prevent body scrolling while modal is open
    document.body.style.overflow = 'hidden';
  }

  /**
   * Hides the modal
   * @public
   */
  hide() {
    this.#modalElement.style.display = 'none';
    this.#isVisible = false;
    
    // Restore body scrolling
    document.body.style.overflow = '';
  }

  /**
   * Destroys the modal instance and removes it from the DOM
   * @public
   */
  destroy() {
    // Remove from DOM
    if (this.#modalElement && this.#modalElement.parentNode) {
      this.#modalElement.parentNode.removeChild(this.#modalElement);
    }
    
    // Clean up references
    this.#modalElement = null;
    this.#overlayElement = null;
    this.#contentElement = null;
    this.#closeButton = null;
  }
}

// Create a singleton instance
const explanationModal = new ExplanationModal();

/**
 * Show explanation modal with the provided text
 * @param {string} explanationText - The explanation text to display
 */
function showExplanation(explanationText) {
  explanationModal.show(explanationText);
}

// Export for use in other modules
window.explanationModal = explanationModal;
window.showExplanation = showExplanation; 