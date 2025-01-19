document.addEventListener('DOMContentLoaded', function() {
    const list = document.querySelectorAll('.user-navigation .list');
    const sectionContent = document.getElementById('section-content');
    const telegramId = document.querySelector('.page-wrapper').getAttribute('data-telegram-id');
    
    function activeLink() {
        list.forEach((item) => item.classList.remove('active'));
        this.classList.add('active');
        
        const section = this.getAttribute('data-section');
        console.log('Switching to section:', section);
        console.log('Telegram ID:', telegramId);
        fetch(`/users/section/${section}/?telegram_id=${telegramId}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.text();
            })
            .then(html => {
                sectionContent.innerHTML = html;
            })
            .catch(error => {
                console.error('Error:', error);
                sectionContent.innerHTML = '<div class="alert alert-danger">Ошибка загрузки содержимого</div>';
            });
    }
    
    list.forEach((item) => item.addEventListener('click', activeLink));
}); 