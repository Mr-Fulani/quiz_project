document.addEventListener('DOMContentLoaded', function() {
    const cards = document.querySelectorAll('.container span');
    
    cards.forEach(card => {
        card.addEventListener('click', function() {
            const quizType = this.querySelector('img').alt.split(' ')[0].toLowerCase();
            // Здесь можно добавить переход к конкретному квизу
            console.log(`Selected quiz: ${quizType}`);
        });
    });
}); 