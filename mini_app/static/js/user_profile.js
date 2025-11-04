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
        
        // Показываем кнопку "Написать", если профиль публичный и есть username
        if (userData.is_profile_public && userData.username) {
            const writeBtn = document.getElementById('write-message-btn');
            if (writeBtn) {
                writeBtn.style.display = 'flex';
                writeBtn.onclick = () => openTelegramChat(userData.username);
            }
        } else {
            // Скрываем кнопку для приватных профилей или если нет username
            const writeBtn = document.getElementById('write-message-btn');
            if (writeBtn) {
                writeBtn.style.display = 'none';
            }
        }
        
        // Обработчик кнопки "Назад"
        const backBtn = document.getElementById('back-btn');
        if (backBtn) {
            backBtn.onclick = () => goBack();
        }
        
        // Настраиваем обработчики для аватарок
        setupAvatarHandlers(userData);
        
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
        
        // Устанавливаем аватар с fallback на default
        if (avatar) {
            if (userData.avatar) {
                console.log('🖼️ [Private] Устанавливаем аватар:', userData.avatar);
                avatar.src = userData.avatar;
                avatar.onerror = function() {
                    console.log('❌ [Private] Ошибка загрузки аватара, используем default');
                    this.src = '/static/images/default_avatar.png';
                };
            } else {
                console.log('⚠️ [Private] Нет аватара, используем default');
                avatar.src = '/static/images/default_avatar.png';
            }
        }
        
        if (name) {
            name.textContent = userData.full_name || `${userData.first_name || ''} ${userData.last_name || ''}`.trim() || 'Пользователь';
        }
        
        // Скрываем username для приватных профилей
        if (username) {
            if (userData.username) {
                username.textContent = `@${userData.username}`;
                username.style.display = 'block';
            } else {
                // Для скрытых профилей не показываем username
                username.style.display = 'none';
            }
        }
        
        // Обработчик кнопки "Назад"
        const backBtn = document.getElementById('back-to-top-users-btn');
        if (backBtn) {
            backBtn.onclick = () => goBack();
        }
        
        // Настраиваем обработчики для аватарок
        setupAvatarHandlers(userData);
    }
    
    /**
     * Форматирование времени "был онлайн X назад"
     */
    function formatLastSeen(lastSeenDate) {
        if (!lastSeenDate) return null;
        
        const now = new Date();
        const lastSeen = new Date(lastSeenDate);
        const diffMs = now - lastSeen;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);
        
        const translations = window.translations || {};
        
        if (diffMins < 1) {
            return translations.just_now || 'только что';
        } else if (diffMins < 60) {
            const unit = window.currentLanguage === 'en' ? 
                (diffMins === 1 ? 'minute' : 'minutes') :
                (diffMins === 1 ? 'минуту' : diffMins < 5 ? 'минуты' : 'минут');
            return window.currentLanguage === 'en' ? 
                `${diffMins} ${unit} ago` : 
                `${diffMins} ${unit} назад`;
        } else if (diffHours < 24) {
            const unit = window.currentLanguage === 'en' ? 
                (diffHours === 1 ? 'hour' : 'hours') :
                (diffHours === 1 ? 'час' : diffHours < 5 ? 'часа' : 'часов');
            return window.currentLanguage === 'en' ? 
                `${diffHours} ${unit} ago` : 
                `${diffHours} ${unit} назад`;
        } else if (diffDays < 7) {
            const unit = window.currentLanguage === 'en' ? 
                (diffDays === 1 ? 'day' : 'days') :
                (diffDays === 1 ? 'день' : diffDays < 5 ? 'дня' : 'дней');
            return window.currentLanguage === 'en' ? 
                `${diffDays} ${unit} ago` : 
                `${diffDays} ${unit} назад`;
        } else {
            const weeks = Math.floor(diffDays / 7);
            const unit = window.currentLanguage === 'en' ? 
                (weeks === 1 ? 'week' : 'weeks') :
                (weeks === 1 ? 'неделю' : weeks < 5 ? 'недели' : 'недель');
            return window.currentLanguage === 'en' ? 
                `${weeks} ${unit} ago` : 
                `${weeks} ${unit} назад`;
        }
    }
    
    /**
     * Обновление заголовка профиля
     */
    function updateProfileHeader(userData) {
        const avatar = document.getElementById('profile-avatar');
        const name = document.getElementById('profile-name');
        const username = document.getElementById('profile-username');
        
        // Устанавливаем аватар с fallback на default
        if (avatar) {
            if (userData.avatar) {
                console.log('🖼️ Устанавливаем аватар:', userData.avatar);
                avatar.src = userData.avatar;
                avatar.onerror = function() {
                    console.log('❌ Ошибка загрузки аватара, используем default');
                    this.src = '/static/images/default_avatar.png';
                };
            } else {
                console.log('⚠️ Нет аватара, используем default');
                avatar.src = '/static/images/default_avatar.png';
            }
        }
        
        if (name) {
            name.textContent = userData.full_name || `${userData.first_name || ''} ${userData.last_name || ''}`.trim() || 'Пользователь';
        }
        
        // Скрываем username для приватных профилей
        if (username) {
            if (userData.username) {
                username.textContent = `@${userData.username}`;
                username.style.display = 'block';
            } else {
                // Для скрытых профилей не показываем username
                username.style.display = 'none';
            }
        }
        
        // Обновляем статус онлайн
        const onlineIndicator = document.getElementById('profile-online-indicator');
        const onlineStatus = document.getElementById('profile-online-status');
        
        if (userData.is_online) {
            // Пользователь онлайн
            if (onlineIndicator) {
                onlineIndicator.style.display = 'block';
            }
            if (onlineStatus) {
                const onlineText = window.currentLanguage === 'en' ? 'Online' : 'В сети';
                onlineStatus.textContent = onlineText;
                onlineStatus.classList.add('is-online');
            }
        } else if (userData.last_seen) {
            // Пользователь был онлайн недавно
            if (onlineIndicator) {
                onlineIndicator.style.display = 'none';
            }
            if (onlineStatus) {
                const lastSeenText = formatLastSeen(userData.last_seen);
                const prefix = window.currentLanguage === 'en' ? 'Last seen' : 'Был в сети';
                onlineStatus.textContent = `${prefix} ${lastSeenText}`;
                onlineStatus.classList.remove('is-online');
            }
        } else {
            // Нет данных об активности
            if (onlineIndicator) {
                onlineIndicator.style.display = 'none';
            }
            if (onlineStatus) {
                onlineStatus.textContent = '';
            }
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
     * Возврат назад (к списку топ-пользователей или к комментариям)
     */
    function goBack() {
        console.log('🔙🔙🔙 GOBACK ВЫЗВАН 🔙🔙🔙');
        
        // Проверяем параметры возврата из URL
        const urlParams = new URLSearchParams(window.location.search);
        const returnTo = urlParams.get('return_to');
        const subtopicId = urlParams.get('subtopic_id');
        const translationId = urlParams.get('translation_id');
        
        // Если пришли из комментариев, возвращаемся на страницу задач
        if (returnTo === 'comments' && subtopicId) {
            console.log('📝 Возврат из комментариев на страницу задач');
            const currentLang = urlParams.get('lang') || window.currentLanguage || 'ru';
            const targetUrl = `/subtopic/${subtopicId}/tasks?lang=${currentLang}`;
            console.log('🚀 Переход на:', targetUrl);
            window.location.href = targetUrl;
            return;
        }
        
        // Стандартная логика возврата на топ-пользователей
        // Проверяем, есть ли сохраненные фильтры
        const savedFilters = sessionStorage.getItem('topUsersFilters');
        console.log('🔍 savedFilters из sessionStorage:', savedFilters);
        
        const currentLang = window.currentLanguage || 'ru';
        let targetUrl = `/top_users?lang=${currentLang}`;
        
        if (savedFilters) {
            try {
                const filters = JSON.parse(savedFilters);
                console.log('📦 Распарсенные фильтры:', filters);
                
                const urlParams = new URLSearchParams();
                
                // Добавляем язык
                urlParams.set('lang', currentLang);
                
                // Добавляем фильтры
                if (filters.gender) {
                    urlParams.set('gender', filters.gender);
                    console.log('✅ Добавлен фильтр gender:', filters.gender);
                }
                if (filters.age) {
                    urlParams.set('age', filters.age);
                    console.log('✅ Добавлен фильтр age:', filters.age);
                }
                if (filters.language) {
                    urlParams.set('language_pref', filters.language);
                    console.log('✅ Добавлен фильтр language_pref:', filters.language);
                }
                if (filters.online) {
                    urlParams.set('online_only', filters.online);
                    console.log('✅ Добавлен фильтр online_only:', filters.online);
                }
                
                targetUrl = `/top_users?${urlParams.toString()}`;
                console.log('🎯 Итоговый URL для возврата:', targetUrl);
            } catch (e) {
                console.error('❌ Ошибка при восстановлении URL с фильтрами:', e);
            }
        } else {
            console.log('⚠️ Нет сохраненных фильтров, возврат на чистую страницу');
        }
        
        console.log('🚀 Переход на:', targetUrl);
        window.location.href = targetUrl;
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
     * Открытие модального окна с галереей аватарок
     */
    function openAvatarModal(avatars, startIndex = 0) {
        console.log('🖼️ Открытие модального окна с аватарками, startIndex:', startIndex);
        
        if (!avatars || avatars.length === 0) {
            console.log('⚠️ Нет аватарок для отображения');
            return;
        }
        
        const backdrop = document.getElementById('avatar-modal-backdrop');
        const modal = document.getElementById('avatar-modal');
        const swiperWrapper = document.getElementById('avatar-swiper-wrapper');
        
        if (!backdrop || !modal || !swiperWrapper) {
            console.error('❌ Элементы модального окна не найдены');
            return;
        }
        
        // Очищаем предыдущие слайды
        swiperWrapper.innerHTML = '';
        
        // Создаем слайды для каждой аватарки
        avatars.forEach((avatar, index) => {
            const slide = document.createElement('div');
            slide.className = 'swiper-slide';
            
            const img = document.createElement('img');
            img.className = 'avatar-image';
            img.src = avatar.image_url || avatar.image;
            img.alt = `Avatar ${index + 1}`;
            
            // Добавляем класс для GIF
            if (avatar.is_gif) {
                img.classList.add('gif');
            }
            
            slide.appendChild(img);
            swiperWrapper.appendChild(slide);
        });
        
        // Блокируем скролл body
        const scrollY = window.pageYOffset || document.documentElement.scrollTop || 0;
        window.scrollPositionBeforeAvatarModal = scrollY;
        document.body.style.overflow = 'hidden';
        document.body.style.position = 'fixed';
        document.body.style.top = `-${scrollY}px`;
        document.body.style.left = '0';
        document.body.style.right = '0';
        document.body.style.width = '100%';
        
        // Показываем backdrop и модальное окно
        backdrop.classList.add('active');
        modal.classList.add('active');
        
        // Инициализируем Swiper с увеличенной задержкой
        setTimeout(() => {
            console.log('🔧 Проверяем доступность Swiper...');
            console.log('🔧 typeof Swiper:', typeof Swiper);
            console.log('🔧 window.Swiper:', window.Swiper);
            
            if (typeof Swiper !== 'undefined') {
                console.log('🔧 Начинаем инициализацию Avatar Swiper...');
                console.log('📊 Количество слайдов:', swiperWrapper.children.length);
                console.log('📍 Начальный индекс:', startIndex);
                
                // Уничтожаем предыдущий экземпляр Swiper если есть
                if (window.avatarSwiper) {
                    console.log('🗑️ Уничтожаем предыдущий Swiper');
                    window.avatarSwiper.destroy(true, true);
                    window.avatarSwiper = null;
                }
                
                // Проверяем что элементы существуют
                const swiperEl = document.getElementById('avatar-swiper');
                if (!swiperEl) {
                    console.error('❌ Swiper элемент не найден!');
                    return;
                }
                
                console.log('✅ Swiper элемент найден, создаем экземпляр...');
                
                window.avatarSwiper = new Swiper('#avatar-swiper', {
                    slidesPerView: 1,
                    spaceBetween: 0,
                    centeredSlides: true,
                    loop: false, // Отключаем loop для отладки
                    effect: 'slide',
                    speed: 300,
                    initialSlide: startIndex,
                    observer: true,
                    observeParents: true,
                    watchOverflow: true,
                    touchRatio: 1,
                    touchAngle: 45,
                    simulateTouch: true,
                    allowTouchMove: true,
                    navigation: {
                        nextEl: '#avatar-swiper .swiper-button-next',
                        prevEl: '#avatar-swiper .swiper-button-prev',
                    },
                    pagination: {
                        el: '#avatar-swiper .swiper-pagination',
                        clickable: true,
                        type: 'bullets',
                    },
                    on: {
                        init: function() {
                            console.log('✅ Avatar Swiper инициализирован');
                            console.log('   - Активный слайд:', this.activeIndex);
                            console.log('   - Всего слайдов:', this.slides.length);
                            console.log('   - Размеры:', {
                                width: this.width,
                                height: this.height
                            });
                        },
                        slideChange: function() {
                            console.log('🔄 Переключение слайда:', this.activeIndex);
                        },
                        touchStart: function() {
                            console.log('👆 Touch start');
                        },
                        touchMove: function() {
                            console.log('👆 Touch move');
                        },
                        touchEnd: function() {
                            console.log('👆 Touch end');
                        }
                    }
                });
                
                // Принудительное обновление размеров
                requestAnimationFrame(() => {
                    if (window.avatarSwiper) {
                        console.log('🔄 Обновляем Swiper...');
                        window.avatarSwiper.update();
                        window.avatarSwiper.updateSize();
                        window.avatarSwiper.updateSlides();
                        window.avatarSwiper.updateProgress();
                        
                        console.log('✅ Avatar Swiper полностью обновлен');
                        console.log('   - Финальный слайд:', window.avatarSwiper.activeIndex);
                        console.log('   - allowTouchMove:', window.avatarSwiper.params.allowTouchMove);
                    }
                });
                
            } else {
                console.error('❌ Swiper library not found');
                console.log('🔄 Попытка загрузить Swiper из CDN...');
                
                // Пытаемся загрузить Swiper из CDN
                const swiperScript = document.createElement('script');
                swiperScript.src = 'https://cdn.jsdelivr.net/npm/swiper@11/swiper-bundle.min.js';
                swiperScript.onload = () => {
                    console.log('✅ Swiper загружен из CDN, повторная инициализация...');
                    // Повторяем инициализацию после загрузки
                    setTimeout(() => {
                        if (typeof Swiper !== 'undefined') {
                            window.avatarSwiper = new Swiper('#avatar-swiper', {
                                slidesPerView: 1,
                                spaceBetween: 0,
                                centeredSlides: true,
                                loop: false,
                                effect: 'slide',
                                speed: 300,
                                initialSlide: startIndex,
                                observer: true,
                                observeParents: true,
                                watchOverflow: true,
                                touchRatio: 1,
                                touchAngle: 45,
                                simulateTouch: true,
                                allowTouchMove: true,
                                navigation: {
                                    nextEl: '#avatar-swiper .swiper-button-next',
                                    prevEl: '#avatar-swiper .swiper-button-prev',
                                },
                                pagination: {
                                    el: '#avatar-swiper .swiper-pagination',
                                    clickable: true,
                                    type: 'bullets',
                                },
                                on: {
                                    init: function() {
                                        console.log('✅ Avatar Swiper инициализирован после загрузки CDN');
                                    }
                                }
                            });
                        }
                    }, 100);
                };
                swiperScript.onerror = () => {
                    console.error('❌ Не удалось загрузить Swiper из CDN');
                };
                document.head.appendChild(swiperScript);
            }
        }, 200);
    }
    
    /**
     * Закрытие модального окна с аватарками
     */
    function closeAvatarModal() {
        console.log('🚪 Закрытие модального окна с аватарками');
        
        const backdrop = document.getElementById('avatar-modal-backdrop');
        const modal = document.getElementById('avatar-modal');
        
        if (backdrop) {
            backdrop.classList.remove('active');
        }
        
        if (modal) {
            modal.classList.remove('active');
        }
        
        // Уничтожаем Swiper
        if (window.avatarSwiper) {
            window.avatarSwiper.destroy(true, true);
            window.avatarSwiper = null;
        }
        
        // Восстанавливаем скролл body
        document.body.style.overflow = '';
        document.body.style.position = '';
        document.body.style.top = '';
        document.body.style.left = '';
        document.body.style.right = '';
        document.body.style.width = '';
        
        if (window.scrollPositionBeforeAvatarModal !== undefined) {
            window.scrollTo(0, window.scrollPositionBeforeAvatarModal);
        }
    }
    
    /**
     * Настройка обработчиков для аватарки
     */
    function setupAvatarHandlers(userData) {
        console.log('🖼️ Настройка обработчиков для аватарки');
        
        const avatar = document.getElementById('profile-avatar');
        const privateAvatar = document.getElementById('private-avatar');
        
        // Проверяем наличие аватарок
        let avatars = userData.avatars || [];
        
        // Если нет аватарок в новой модели, но есть старое поле avatar, используем его
        if (avatars.length === 0 && userData.avatar) {
            console.log('📸 Используем старое поле avatar:', userData.avatar);
            avatars = [{
                id: 0,
                image_url: userData.avatar,
                image: userData.avatar,
                order: 0,
                is_gif: userData.avatar.toLowerCase().endsWith('.gif')
            }];
        }
        
        console.log('📸 Количество аватарок для отображения:', avatars.length);
        
        if (avatars.length > 0) {
            // Делаем аватарку кликабельной
            if (avatar) {
                avatar.style.cursor = 'pointer';
                // Удаляем предыдущие обработчики
                const newAvatar = avatar.cloneNode(true);
                avatar.parentNode.replaceChild(newAvatar, avatar);
                
                newAvatar.addEventListener('click', () => {
                    console.log('🖱️ Клик по аватарке');
                    openAvatarModal(avatars, 0);
                });
            }
            
            if (privateAvatar) {
                privateAvatar.style.cursor = 'pointer';
                // Удаляем предыдущие обработчики
                const newPrivateAvatar = privateAvatar.cloneNode(true);
                privateAvatar.parentNode.replaceChild(newPrivateAvatar, privateAvatar);
                
                newPrivateAvatar.addEventListener('click', () => {
                    console.log('🖱️ Клик по приватной аватарке');
                    openAvatarModal(avatars, 0);
                });
            }
        }
        
        // Настраиваем кнопку закрытия модального окна
        const closeBtn = document.getElementById('avatar-modal-close');
        const backdrop = document.getElementById('avatar-modal-backdrop');
        
        if (closeBtn) {
            closeBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                closeAvatarModal();
            });
        }
        
        if (backdrop) {
            backdrop.addEventListener('click', closeAvatarModal);
        }
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

