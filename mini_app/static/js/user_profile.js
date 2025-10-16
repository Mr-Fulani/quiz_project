/**
 * JavaScript модуль для просмотра профиля пользователя в Telegram Mini App.
 * Обеспечивает загрузку и отображение публичных и приватных профилей.
 */

(function(window) {
    console.log('🚀 User Profile.js загружен!');
    
    let currentUserData = null;
    
    /**
     * Получение telegram_id пользователя из URL
     */
    function getUserTelegramId() {
        // Извлекаем telegram_id из URL: /user_profile/{telegram_id}
        const pathParts = window.location.pathname.split('/');
        const telegramId = pathParts[pathParts.length - 1];
        const parsed = parseInt(telegramId, 10);
        
        console.log('🔍 Извлечение telegram_id из URL:', {
            pathname: window.location.pathname,
            pathParts: pathParts,
            telegramId: telegramId,
            parsed: parsed
        });
        
        return parsed || null;
    }
    
    /**
     * Загрузка профиля пользователя с сервера
     */
    async function loadUserProfile() {
        console.log('🚀🚀🚀 ФУНКЦИЯ loadUserProfile ВЫЗВАНА!');
        
        const telegramId = getUserTelegramId();
        console.log('🔍 Получен telegram_id:', telegramId);
        
        if (!telegramId) {
            console.error('❌ Telegram ID не найден');
            showError('Ошибка: не указан пользователь');
            return;
        }
        
        console.log(`📥 Загружаем профиль пользователя ${telegramId}`);
        
        try {
            // Запрашиваем данные профиля через mini_app API
            const response = await fetch(`/api/user-profile/${telegramId}`, {
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            if (!response.ok) {
                console.error(`❌ Ошибка загрузки профиля: ${response.status}`);
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const userData = await response.json();
            console.log('✅ Данные профиля получены:', userData);
            console.log('🔍 is_profile_public:', userData.is_profile_public);
            
            currentUserData = userData;
            
            // Скрываем лоадер
            console.log('🔄 Вызываем hideLoader()...');
            hideLoader();
            
            // Проверяем тип профиля и отображаем соответствующий контент
            if (userData.is_profile_public) {
                console.log('✅ Профиль публичный, вызываем renderPublicProfile()');
                renderPublicProfile(userData);
            } else {
                console.log('🔒 Профиль приватный, вызываем renderPrivateProfile()');
                renderPrivateProfile(userData);
            }
            
        } catch (error) {
            console.error('❌ Ошибка при загрузке профиля:', error);
            hideLoader();
            showError('Не удалось загрузить профиль пользователя');
        }
    }
    
    /**
     * Отображение публичного профиля
     */
    function renderPublicProfile(userData) {
        console.log('👁️ Отображаем публичный профиль');
        console.log('👁️ Данные для рендера:', userData);
        
        const container = document.getElementById('public-profile-container');
        console.log('👁️ Контейнер найден:', container);
        
        if (!container) {
            console.error('❌ Контейнер публичного профиля не найден');
            return;
        }
        
        // Показываем контейнер публичного профиля
        console.log('👁️ Показываем контейнер публичного профиля через класс visible');
        container.classList.add('visible');
        
        // Обновляем основную информацию
        updateProfileHeader(userData);
        
        // Обновляем профессиональную информацию
        updateProfessionalInfo(userData);
        
        // Обновляем статистику
        updateStatistics(userData);
        
        // Обновляем социальные ссылки
        updateSocialLinks(userData);
        
        // Показываем кнопку "Написать", если есть username
        if (userData.username) {
            const writeBtn = document.getElementById('write-message-btn');
            if (writeBtn) {
                writeBtn.style.display = 'flex';
                writeBtn.onclick = () => openTelegramChat(userData.username);
            }
        }
        
        // Обработчик кнопки "Назад"
        const backBtn = document.getElementById('back-btn');
        if (backBtn) {
            backBtn.onclick = () => goBack();
        }
        
        console.log('✅✅✅ ПУБЛИЧНЫЙ ПРОФИЛЬ ОТРИСОВАН УСПЕШНО!');
    }
    
    /**
     * Отображение приватного профиля
     */
    function renderPrivateProfile(userData) {
        console.log('🔒 Отображаем приватный профиль');
        
        const container = document.getElementById('private-profile-container');
        if (!container) {
            console.error('❌ Контейнер приватного профиля не найден');
            return;
        }
        
        // Показываем контейнер приватного профиля
        console.log('🔒 Показываем контейнер приватного профиля через класс visible');
        container.classList.add('visible');
        
        // Обновляем базовую информацию
        const avatar = document.getElementById('private-avatar');
        const name = document.getElementById('private-name');
        const username = document.getElementById('private-username');
        
        if (avatar && userData.avatar) {
            avatar.src = userData.avatar;
        }
        
        if (name) {
            name.textContent = userData.full_name || `${userData.first_name || ''} ${userData.last_name || ''}`.trim() || 'Пользователь';
        }
        
        if (username && userData.username) {
            username.textContent = `@${userData.username}`;
        }
        
        // Обработчик кнопки "Назад"
        const backBtn = document.getElementById('back-to-top-users-btn');
        if (backBtn) {
            backBtn.onclick = () => goBack();
        }
    }
    
    /**
     * Обновление заголовка профиля
     */
    function updateProfileHeader(userData) {
        const avatar = document.getElementById('profile-avatar');
        const name = document.getElementById('profile-name');
        const username = document.getElementById('profile-username');
        
        if (avatar && userData.avatar) {
            avatar.src = userData.avatar;
            avatar.onerror = function() {
                this.src = '/static/images/default_avatar.png';
            };
        }
        
        if (name) {
            name.textContent = userData.full_name || `${userData.first_name || ''} ${userData.last_name || ''}`.trim() || 'Пользователь';
        }
        
        if (username && userData.username) {
            username.textContent = `@${userData.username}`;
        }
    }
    
    /**
     * Обновление профессиональной информации
     */
    function updateProfessionalInfo(userData) {
        // Пол
        const genderElement = document.getElementById('profile-gender');
        if (genderElement) {
            if (userData.gender) {
                const genderMap = {
                    'male': window.translations?.male || 'Мужской',
                    'female': window.translations?.female || 'Женский'
                };
                genderElement.textContent = genderMap[userData.gender] || userData.gender;
            } else {
                genderElement.textContent = window.translations?.not_specified || 'Не указан';
            }
        }
        
        // Дата рождения
        const birthDateElement = document.getElementById('profile-birth-date');
        if (birthDateElement) {
            if (userData.birth_date) {
                const date = new Date(userData.birth_date);
                const currentLang = window.currentLanguage || 'ru';
                const locale = currentLang === 'en' ? 'en-US' : 'ru-RU';
                
                birthDateElement.textContent = date.toLocaleDateString(locale, {
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric'
                });
            } else {
                birthDateElement.textContent = window.translations?.not_specified || 'Не указана';
            }
        }
        
        // Грейд
        const gradeElement = document.getElementById('profile-grade');
        if (gradeElement) {
            if (userData.grade) {
                const gradeMap = {
                    'junior': window.translations?.grade_junior || 'Junior',
                    'middle': window.translations?.grade_middle || 'Middle',
                    'senior': window.translations?.grade_senior || 'Senior'
                };
                const gradeText = gradeMap[userData.grade] || userData.grade;
                
                // Добавляем классы для эффектов в зависимости от грейда
                gradeElement.className = `info-value grade-${userData.grade}`;
                gradeElement.textContent = gradeText;
            } else {
                gradeElement.className = 'info-value grade-none';
                gradeElement.textContent = window.translations?.not_specified || 'Не указан';
            }
        }
        
        // Технологии
        const technologiesElement = document.getElementById('profile-technologies');
        if (technologiesElement) {
            if (userData.programming_languages && userData.programming_languages.length > 0) {
                technologiesElement.innerHTML = userData.programming_languages
                    .map(tech => `<span class="technology-tag">${tech}</span>`)
                    .join('');
            } else {
                technologiesElement.innerHTML = `<span class="no-data">${window.translations?.no_technologies || 'Технологии не указаны'}</span>`;
            }
        }
    }
    
    /**
     * Обновление статистики
     */
    function updateStatistics(userData) {
        // Всего вопросов
        const totalQuizzesElement = document.getElementById('profile-total-quizzes');
        if (totalQuizzesElement) {
            totalQuizzesElement.textContent = userData.total_quizzes || 0;
        }
        
        // Правильных ответов
        const correctAnswersElement = document.getElementById('profile-correct-answers');
        if (correctAnswersElement) {
            correctAnswersElement.textContent = userData.correct_answers || 0;
        }
        
        // Неправильных ответов
        const incorrectAnswersElement = document.getElementById('profile-incorrect-answers');
        if (incorrectAnswersElement) {
            incorrectAnswersElement.textContent = userData.incorrect_answers || 0;
        }
        
        // Точность
        const successRateElement = document.getElementById('profile-success-rate');
        if (successRateElement) {
            const successRate = userData.success_rate || 0;
            successRateElement.textContent = `${Math.round(successRate)}%`;
        }
        
        // Текущая серия
        const currentStreakElement = document.getElementById('profile-current-streak');
        if (currentStreakElement) {
            currentStreakElement.textContent = userData.current_streak || 0;
        }
        
        // Лучшая серия
        const bestStreakElement = document.getElementById('profile-best-streak');
        if (bestStreakElement) {
            bestStreakElement.textContent = userData.best_streak || 0;
        }
    }
    
    /**
     * Обновление социальных ссылок
     */
    function updateSocialLinks(userData) {
        const container = document.getElementById('social-links-container');
        if (!container) return;
        
        if (!userData.social_links || userData.social_links.length === 0) {
            container.innerHTML = `<p class="social-empty">${window.translations?.no_social_links || 'Социальные сети не указаны.'}</p>`;
            return;
        }
        
        // Маппинг названий на Font Awesome иконки (как в profile.js)
        const getIconClass = (name) => {
            switch (name) {
                case 'Веб-сайт':
                    return 'fas fa-globe';
                case 'Telegram':
                    return 'fab fa-telegram';
                case 'GitHub':
                    return 'fab fa-github';
                case 'LinkedIn':
                    return 'fab fa-linkedin';
                case 'Instagram':
                    return 'fab fa-instagram';
                case 'Facebook':
                    return 'fab fa-facebook';
                case 'YouTube':
                    return 'fab fa-youtube';
                default:
                    return 'fas fa-link';
            }
        };
        
        container.innerHTML = '<div class="social-links-list">' +
            userData.social_links.map(link => {
                const iconClass = getIconClass(link.name);
                return `
                    <a href="${link.url}" target="_blank" class="social-link" rel="noopener noreferrer">
                        <div class="social-icon"><i class="${iconClass}"></i></div>
                        <div class="social-info">
                            <div class="social-name">${link.name}</div>
                            <div class="social-url">${link.url.replace(/^(https?:\/\/)?(www\.)?/, '')}</div>
                        </div>
                    </a>
                `;
            }).join('') +
            '</div>';
    }
    
    /**
     * Открытие чата в Telegram
     */
    function openTelegramChat(username) {
        console.log(`📱 Открываем чат с пользователем @${username}`);
        
        // Удаляем @ если он есть
        const cleanUsername = username.replace('@', '');
        
        // Открываем чат в Telegram
        const tg = window.Telegram?.WebApp;
        if (tg) {
            try {
                // Используем Telegram WebApp API для открытия чата
                window.open(`https://t.me/${cleanUsername}`, '_blank');
            } catch (e) {
                console.error('❌ Ошибка при открытии чата:', e);
                window.open(`https://t.me/${cleanUsername}`, '_blank');
            }
        } else {
            window.open(`https://t.me/${cleanUsername}`, '_blank');
        }
    }
    
    /**
     * Возврат назад (к списку топ-пользователей)
     */
    function goBack() {
        console.log('🔙 Возврат назад');
        window.location.href = '/top_users';
    }
    
    /**
     * Скрытие лоадера
     */
    function hideLoader() {
        console.log('🔄 Скрываем лоадер...');
        const loader = document.getElementById('user-profile-loader');
        console.log('🔍 Loader элемент:', loader);
        if (loader) {
            loader.classList.add('hidden');
            console.log('✅ Loader скрыт через класс hidden');
        } else {
            console.error('❌ Loader элемент не найден!');
        }
    }
    
    /**
     * Отображение ошибки
     */
    function showError(message) {
        alert(message);
        // Возвращаемся назад после ошибки
        setTimeout(() => goBack(), 2000);
    }
    
    /**
     * Инициализация при загрузке страницы
     */
    function init() {
        console.log('🎬 Инициализация страницы просмотра профиля');
        
        // Загружаем профиль пользователя
        loadUserProfile();
    }
    
    /**
     * Глобальная функция для переинициализации при SPA навигации
     */
    window.reinitializeUserProfilePage = function() {
        console.log('🔄 Переинициализация страницы просмотра профиля');
        init();
    };
    
    // Инициализация при загрузке DOM
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})(window);

