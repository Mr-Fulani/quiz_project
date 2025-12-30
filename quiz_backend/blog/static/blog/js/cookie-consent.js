/**
 * Cookie Consent Manager
 * Handles user consent for analytics cookies (Google Analytics, Yandex Metrika)
 */

(function() {
    'use strict';

    const COOKIE_NAME = 'cookie_consent';
    const COOKIE_EXPIRY_DAYS = 365;
    
    // Get current language from HTML lang attribute or default to 'en'
    function getCurrentLanguage() {
        const htmlLang = document.documentElement.lang || 'en';
        return htmlLang.startsWith('ru') ? 'ru' : 'en';
    }

    // Translations
    const translations = {
        en: {
            title: 'Cookie Consent',
            message: 'We use cookies to analyze site traffic and improve your experience. By clicking "Accept", you consent to our use of cookies.',
            accept: 'Accept',
            reject: 'Reject',
            privacy: 'Privacy Policy'
        },
        ru: {
            title: 'Согласие на использование cookies',
            message: 'Мы используем cookies для анализа трафика сайта и улучшения вашего опыта. Нажимая "Принять", вы соглашаетесь на использование cookies.',
            accept: 'Принять',
            reject: 'Отклонить',
            privacy: 'Политика конфиденциальности'
        }
    };

    // Cookie utilities
    function setCookie(name, value, days) {
        const date = new Date();
        date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
        const expires = 'expires=' + date.toUTCString();
        document.cookie = name + '=' + value + ';' + expires + ';path=/;SameSite=Lax';
    }

    function getCookie(name) {
        const nameEQ = name + '=';
        const ca = document.cookie.split(';');
        for (let i = 0; i < ca.length; i++) {
            let c = ca[i];
            while (c.charAt(0) === ' ') c = c.substring(1, c.length);
            if (c.indexOf(nameEQ) === 0) return c.substring(nameEQ.length, c.length);
        }
        return null;
    }

    // Get consent status
    function getConsentStatus() {
        return getCookie(COOKIE_NAME);
    }

    // Set consent status
    function setConsentStatus(status) {
        setCookie(COOKIE_NAME, status, COOKIE_EXPIRY_DAYS);
    }

    // Check if consent is given
    function hasConsent() {
        const status = getConsentStatus();
        return status === 'accepted';
    }

    // Load analytics scripts if consent is given
    function loadAnalytics() {
        if (!hasConsent()) {
            return;
        }

        // Helper function to load analytics after page load
        function loadAfterPageLoad(callback) {
            if (document.readyState === 'complete') {
                setTimeout(callback, 3000);
            } else {
                window.addEventListener('load', function() {
                    setTimeout(callback, 3000);
                });
            }
        }

        // Load Google Analytics
        const gaId = window.GOOGLE_ANALYTICS_PROPERTY_ID;
        if (gaId) {
            loadAfterPageLoad(function() {
                // Check if already loaded
                if (window.gtag) {
                    console.log('Google Analytics already initialized');
                    return;
                }

                var script = document.createElement('script');
                script.async = true;
                script.src = 'https://www.googletagmanager.com/gtag/js?id=' + gaId;
                document.head.appendChild(script);
                
                script.onload = function() {
                    window.dataLayer = window.dataLayer || [];
                    function gtag(){dataLayer.push(arguments);}
                    window.gtag = gtag;
                    gtag('js', new Date());
                    gtag('config', gaId);
                    console.log('Google Analytics initialized with ID: ' + gaId);
                };
            });
        }

        // Load Yandex Metrika
        const yandexId = window.YANDEX_METRICA_ID;
        if (yandexId) {
            loadAfterPageLoad(function() {
                // Check if already loaded
                if (window.ym && window.ym.a && window.ym.a.length > 0) {
                    console.log('Yandex Metrika already initialized');
                    return;
                }

                (function(m,e,t,r,i,k,a){m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)};
                m[i].l=1*new Date();k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a)})
                (window, document, "script", "https://mc.yandex.ru/metrika/tag.js", "ym");
                ym(yandexId, "init", { clickmap:true, trackLinks:true, accurateTrackBounce:true });
                console.log('Yandex Metrica initialized with ID: ' + yandexId);
            });
        }
    }

    // Create cookie consent banner
    function createBanner() {
        const lang = getCurrentLanguage();
        const t = translations[lang];
        const privacyUrl = window.COOKIE_CONSENT_PRIVACY_URL || '/privacy-policy/';

        const banner = document.createElement('div');
        banner.id = 'cookie-consent-banner';
        banner.className = 'cookie-consent-banner';
        banner.innerHTML = `
            <div class="cookie-consent-content">
                <div class="cookie-consent-text">
                    <h4 class="cookie-consent-title">${t.title}</h4>
                    <p class="cookie-consent-message">${t.message}</p>
                </div>
                <div class="cookie-consent-actions">
                    <a href="${privacyUrl}" class="cookie-consent-link" target="_blank">${t.privacy}</a>
                    <button class="cookie-consent-btn cookie-consent-reject" id="cookie-consent-reject">${t.reject}</button>
                    <button class="cookie-consent-btn cookie-consent-accept" id="cookie-consent-accept">${t.accept}</button>
                </div>
            </div>
        `;

        document.body.appendChild(banner);

        // Add event listeners
        document.getElementById('cookie-consent-accept').addEventListener('click', function() {
            setConsentStatus('accepted');
            hideBanner();
            loadAnalytics();
        });

        document.getElementById('cookie-consent-reject').addEventListener('click', function() {
            setConsentStatus('rejected');
            hideBanner();
        });
    }

    // Hide banner
    function hideBanner() {
        const banner = document.getElementById('cookie-consent-banner');
        if (banner) {
            banner.classList.add('cookie-consent-hidden');
            setTimeout(function() {
                banner.remove();
            }, 300);
        }
    }

    // Show banner if consent not given
    function init() {
        const consentStatus = getConsentStatus();
        
        if (!consentStatus) {
            // No consent given yet, show banner
            createBanner();
        } else if (hasConsent()) {
            // Consent already given, load analytics
            loadAnalytics();
        }
        // If rejected, do nothing (analytics won't load)
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Expose functions globally for potential manual control
    window.CookieConsent = {
        hasConsent: hasConsent,
        setConsent: function(status) {
            setConsentStatus(status);
            if (status === 'accepted') {
                loadAnalytics();
            }
        },
        showBanner: createBanner
    };
})();

