/**
 * settings.js
 * Инициализация логики для страницы настроек.
 */

console.log('🟢 settings.js LOADED!');

class SettingsPage {
    constructor() {
        this.retryCount = 0;
        this.maxRetries = 20;
        this.init();
    }
    
    init() {
        console.log('🔧 SettingsPage: Initializing...');
        // Проверяем админ доступ с задержкой для загрузки window.currentUser
        this.checkAdminAccessWithRetry();
    }
    
    checkAdminAccess() {
        try {
            const profileData = window.currentUser;
            console.log('🔍 [checkAdminAccess] Starting check...');
            console.log('🔍 [checkAdminAccess] window.currentUser:', profileData);
            
            if (!profileData) {
                console.log('⏳ [checkAdminAccess] window.currentUser not yet loaded');
                return false;
            }
            
            console.log('🔍 [checkAdminAccess] is_admin value:', profileData.is_admin, 'type:', typeof profileData.is_admin);
            
            if (profileData.is_admin === true) {
                console.log('✅ [checkAdminAccess] User IS ADMIN! Showing button...');
                const adminPanelContainer = document.getElementById('admin-panel-container');
                console.log('🔍 [checkAdminAccess] Container found:', !!adminPanelContainer);
                
                if (adminPanelContainer) {
                    adminPanelContainer.style.display = 'block';
                    console.log('✅ [checkAdminAccess] ✨ ADMIN PANEL BUTTON DISPLAYED! ✨');
                    return true;
                } else {
                    console.error('❌ [checkAdminAccess] Container #admin-panel-container NOT FOUND in DOM!');
                    return false;
                }
            } else {
                console.log('⚠️ [checkAdminAccess] User is NOT admin');
                console.log('   ℹ️ is_admin is:', profileData.is_admin, 'Expected: true');
                return false;
            }
        } catch (error) {
            console.error('❌ [checkAdminAccess] ERROR:', error);
            return false;
        }
    }
    
    checkAdminAccessWithRetry() {
        console.log(`🔄 [checkAdminAccessWithRetry] Attempt ${this.retryCount + 1}/${this.maxRetries}`);
        
        const success = this.checkAdminAccess();
        
        if (success) {
            console.log('✅ [checkAdminAccessWithRetry] Admin access check SUCCESSFUL!');
            return;
        }
        
        if (this.retryCount < this.maxRetries) {
            this.retryCount++;
            setTimeout(() => this.checkAdminAccessWithRetry(), 300);
        } else {
            console.log('⚠️ [checkAdminAccessWithRetry] Max retries reached, giving up');
        }
    }
}

// Глобальная функция для инициализации (вызывается из base.html)
function initSettingsPage() {
    console.log('📊 SettingsPage: initSettingsPage called');
    console.log('📊 window.settingsPageInstance:', window.settingsPageInstance);
    console.log('📊 document.readyState:', document.readyState);
    
    if (window.settingsPageInstance) {
        console.log('⚠️ SettingsPage already initialized, skipping...');
        return;
    }
    
    console.log('🚀 Creating new SettingsPage instance...');
    window.settingsPageInstance = new SettingsPage();
}

// Проверяем состояние документа
if (document.readyState === 'loading') {
    console.log('📊 SettingsPage: DOM loading, adding DOMContentLoaded listener');
    document.addEventListener('DOMContentLoaded', initSettingsPage);
} else {
    console.log('📊 SettingsPage: DOM already loaded, initializing immediately');
    initSettingsPage();
}
