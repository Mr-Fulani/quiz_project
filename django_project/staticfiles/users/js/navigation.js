document.addEventListener('DOMContentLoaded', function() {
    const list = document.querySelectorAll('.user-navigation .list');
    
    function activeLink() {
        list.forEach((item) => 
            item.classList.remove('active'));
        this.classList.add('active');
    }
    
    list.forEach((item) =>
        item.addEventListener('click', activeLink));
}); 