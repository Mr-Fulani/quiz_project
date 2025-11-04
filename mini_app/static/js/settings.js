/**
 * settings.js
 * Инициализация логики для страницы настроек.
 */

console.log('═══════════════════════════════════════════════════');
console.log('🟢 [SETTINGS] settings.js LOADED!');
console.log('═══════════════════════════════════════════════════');

// Предотвращаем повторное объявление класса при SPA-навигации
if (typeof SettingsPage === 'undefined') {
    window.SettingsPage = class SettingsPage {
        constructor() {
            console.log('═══════════════════════════════════════════════════');
            console.log('🏗️ [SETTINGS] SettingsPage constructor called');
            this.retryCount = 0;
            this.maxRetries = 20;
            console.log('🏗️ [SETTINGS] Starting init...');
            this.init();
            console.log('═══════════════════════════════════════════════════');
        }
    
    init() {
        console.log('═══════════════════════════════════════════════════');
        console.log('🔧 [SETTINGS] SettingsPage: Initializing...');
        console.log('🔧 [SETTINGS] window.currentUser:', window.currentUser);
        // Проверяем админ доступ с задержкой для загрузки window.currentUser
        this.checkAdminAccessWithRetry();
        // Применяем локальные пользовательские настройки и навешиваем обработчики
        this.applyLocalSettings();
    }
    
    checkAdminAccess() {
        try {
            const profileData = window.currentUser;
            console.log('═══════════════════════════════════════════════════');
            console.log('🔍 [SETTINGS-CHECK] Starting admin access check...');
            console.log('🔍 [SETTINGS-CHECK] window.currentUser:', profileData);
            console.log('🔍 [SETTINGS-CHECK] typeof window.currentUser:', typeof profileData);
            
            if (!profileData) {
                console.log('⏳ [SETTINGS-CHECK] window.currentUser not yet loaded');
                console.log('═══════════════════════════════════════════════════');
                return false;
            }
            
            console.log('🔍 [SETTINGS-CHECK] is_admin value:', profileData.is_admin);
            console.log('🔍 [SETTINGS-CHECK] is_admin type:', typeof profileData.is_admin);
            console.log('🔍 [SETTINGS-CHECK] Full profile keys:', Object.keys(profileData));
            
            if (profileData.is_admin === true) {
                console.log('✅ [SETTINGS-CHECK] User IS ADMIN! Showing button...');
                const adminPanelContainer = document.getElementById('admin-panel-container');
                console.log('🔍 [SETTINGS-CHECK] Container found:', !!adminPanelContainer);
                console.log('🔍 [SETTINGS-CHECK] Container element:', adminPanelContainer);
                
                if (adminPanelContainer) {
                    const oldDisplay = adminPanelContainer.style.display;
                    adminPanelContainer.style.display = 'block';
                    const newDisplay = adminPanelContainer.style.display;
                    console.log('✅ [SETTINGS-CHECK] ✨ ADMIN PANEL BUTTON DISPLAYED! ✨');
                    console.log('✅ [SETTINGS-CHECK] Display changed:', oldDisplay, '->', newDisplay);
                    console.log('═══════════════════════════════════════════════════');
                    return true;
                } else {
                    console.error('❌ [SETTINGS-CHECK] Container #admin-panel-container NOT FOUND in DOM!');
                    console.log('═══════════════════════════════════════════════════');
                    return false;
                }
            } else {
                console.log('⚠️ [SETTINGS-CHECK] User is NOT admin');
                console.log('   ℹ️ [SETTINGS-CHECK] is_admin is:', profileData.is_admin, 'Expected: true');
                console.log('═══════════════════════════════════════════════════');
                return false;
            }
        } catch (error) {
            console.error('❌ [SETTINGS-CHECK] ERROR:', error);
            console.error('❌ [SETTINGS-CHECK] Stack:', error.stack);
            console.log('═══════════════════════════════════════════════════');
            return false;
        }
    }
    
    checkAdminAccessWithRetry() {
        console.log(`🔄 [SETTINGS-RETRY] Attempt ${this.retryCount + 1}/${this.maxRetries}`);
        
        const success = this.checkAdminAccess();
        
        if (success) {
            console.log('✅ [SETTINGS-RETRY] Admin access check SUCCESSFUL!');
            return;
        }
        
        if (this.retryCount < this.maxRetries) {
            this.retryCount++;
            console.log(`⏳ [SETTINGS-RETRY] Scheduling retry #${this.retryCount} in 300ms...`);
            setTimeout(() => this.checkAdminAccessWithRetry(), 300);
        } else {
            console.log('⚠️ [SETTINGS-RETRY] Max retries reached, giving up');
        }
    }
    
    applyLocalSettings() {
        try {
            // Восстанавливаем состояние переключателя уведомлений из профиля пользователя
            const notificationsToggle = document.getElementById('notifications-toggle');
            if (notificationsToggle && window.currentUser) {
                // Устанавливаем состояние из профиля пользователя
                notificationsToggle.checked = window.currentUser.notifications_enabled !== false;
                
                // Обработчик изменения настройки
                notificationsToggle.addEventListener('change', async function(e) {
                    const isEnabled = e.target.checked;
                    console.log('🔔 [SETTINGS] Изменение настройки уведомлений:', isEnabled);
                    
                    try {
                        // Отправляем обновление на сервер
                        const response = await fetch(`/api/accounts/miniapp-users/update/${window.currentUser.telegram_id}/`, {
                            method: 'PATCH',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({
                                notifications_enabled: isEnabled
                            })
                        });
                        
                        if (response.ok) {
                            console.log('✅ [SETTINGS] Настройка уведомлений сохранена');
                            // Обновляем локальный профиль
                            if (window.currentUser) {
                                window.currentUser.notifications_enabled = isEnabled;
                            }
                            
                            // Показываем уведомление пользователю
                            if (window.Telegram && window.Telegram.WebApp) {
                                window.Telegram.WebApp.showAlert(
                                    isEnabled ? 
                                    'Уведомления включены' : 
                                    'Уведомления отключены'
                                );
                            }
                        } else {
                            console.error('❌ [SETTINGS] Ошибка сохранения настройки уведомлений');
                            // Возвращаем предыдущее состояние
                            notificationsToggle.checked = !isEnabled;
                        }
                    } catch (error) {
                        console.error('❌ [SETTINGS] Исключение при сохранении:', error);
                        // Возвращаем предыдущее состояние
                        notificationsToggle.checked = !isEnabled;
                    }
                });
            }

            // Восстанавливаем выбранный язык и активное состояние кнопки
            const savedLanguage = localStorage.getItem('selectedLanguage');
            if (savedLanguage && savedLanguage !== window.currentLanguage) {
                document.querySelectorAll('.language-btn').forEach(btn => btn.classList.remove('active'));
                const activeBtn = document.querySelector(`[data-lang="${savedLanguage}"]`);
                if (activeBtn) {
                    activeBtn.classList.add('active');
                }
            }
        } catch (e) {
            console.warn('⚠️ [SETTINGS] Failed to apply local settings:', e);
        }
    }
    };
} else {
    console.log('⚠️ [SETTINGS] SettingsPage class already defined, skipping redefinition');
}

// Глобальная функция для инициализации (вызывается из base.html)
function initSettingsPage() {
    console.log('═══════════════════════════════════════════════════');
    console.log('📊 [SETTINGS-INIT] initSettingsPage called');
    console.log('📊 [SETTINGS-INIT] Current pathname:', window.location.pathname);
    console.log('📊 [SETTINGS-INIT] Current URL:', window.location.href);
    console.log('📊 [SETTINGS-INIT] window.settingsPageInstance:', window.settingsPageInstance);
    console.log('📊 [SETTINGS-INIT] document.readyState:', document.readyState);
    
    // Проверяем, что мы на странице настроек
    const isSettingsPage = window.location.pathname === '/settings' || 
                           window.location.pathname.startsWith('/settings?');
    
    console.log('📊 [SETTINGS-INIT] isSettingsPage:', isSettingsPage);
    
    if (!isSettingsPage) {
        console.log('⚠️ [SETTINGS-INIT] Not on settings page, skipping initialization');
        console.log('═══════════════════════════════════════════════════');
        return;
    }
    
    // ВСЕГДА пересоздаем instance при загрузке страницы
    // чтобы проверка админ-прав работала после переключения языка
    if (window.settingsPageInstance) {
        console.log('🔄 [SETTINGS-INIT] SettingsPage exists, recreating for fresh admin check...');
        console.log('🔄 [SETTINGS-INIT] Old instance:', window.settingsPageInstance);
    }
    
    console.log('🚀 [SETTINGS-INIT] Creating new SettingsPage instance...');
    window.settingsPageInstance = new window.SettingsPage();
    console.log('🚀 [SETTINGS-INIT] New instance created:', window.settingsPageInstance);
    console.log('═══════════════════════════════════════════════════');
}

// Проверяем состояние документа
if (document.readyState === 'loading') {
    console.log('📊 SettingsPage: DOM loading, adding DOMContentLoaded listener');
    document.addEventListener('DOMContentLoaded', initSettingsPage);
} else {
    console.log('📊 SettingsPage: DOM already loaded, initializing immediately');
    initSettingsPage();
}
