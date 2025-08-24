// Тестовый скрипт для проверки инициализации пользователя
console.log('🧪 Тестирование инициализации пользователя...');

// Симулируем Telegram WebApp
window.Telegram = {
    WebApp: {
        initData: 'query_id=AAFKpLlIAwAAAEqkuUjJGqj5&user=%7B%22id%22%3A7662576714%2C%22first_name%22%3A%22Development%22%2C%22last_name%22%3A%22%26%20Other%22%2C%22username%22%3A%22Mr_Fulani_Dev%22%2C%22language_code%22%3A%22ru%22%2C%22allows_write_to_pm%22%3Atrue%2C%22photo_url%22%3A%22https%3A//t.me/i/userpic/320/wBRNBCw0eJdlS9v5O6MHIpDBi1r7AkMv_9MuSl5WliJNZ-1vNDIA1jlRI1N2dDCR.svg%22%7D&auth_date=1732400000&hash=test_hash',
        initDataUnsafe: {
            user: {
                id: 7662576714,
                first_name: 'Development',
                last_name: '& Other',
                username: 'Mr_Fulani_Dev',
                language_code: 'ru',
                allows_write_to_pm: true,
                photo_url: 'https://t.me/i/userpic/320/wBRNBCw0eJdlS9v5O6MHIpDBi1r7AkMv_9MuSl5WliJNZ-1vNDIA1jlRI1N2dDCR.svg'
            }
        }
    }
};

console.log('🔧 Симулированный Telegram WebApp создан');
console.log('window.Telegram.WebApp.initData:', window.Telegram.WebApp.initData);
console.log('window.Telegram.WebApp.initDataUnsafe.user.id:', window.Telegram.WebApp.initDataUnsafe.user.id);

// Тестируем initializeUser
if (typeof window.initializeUser === 'function') {
    console.log('✅ initializeUser найден, вызываем...');
    window.initializeUser();
    
    setTimeout(() => {
        console.log('⏰ Результат инициализации:');
        console.log('window.currentUser:', window.currentUser);
        console.log('window.isUserInitialized:', window.isUserInitialized);
        console.log('window.currentUser?.telegram_id:', window.currentUser?.telegram_id);
    }, 2000);
} else {
    console.error('❌ initializeUser не найден!');
}
