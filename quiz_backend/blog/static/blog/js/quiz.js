document.addEventListener('DOMContentLoaded', function() {
    console.log("Script loaded");
    const answers = document.querySelectorAll('.answer-option');
    console.log("Found answers:", answers.length);

    answers.forEach(answer => {
        answer.addEventListener('click', function() {
            console.log("Clicked:", this.textContent);
            const parent = this.parentElement;
            const correctAnswer = parent.dataset.correct;
            const selectedAnswer = this.dataset.answer;
            console.log("Correct:", correctAnswer, "Selected:", selectedAnswer);

            parent.querySelectorAll('.answer-option').forEach(opt => {
                opt.style.pointerEvents = 'none';
            });

            if (selectedAnswer === correctAnswer) {
                this.classList.add('correct');
            } else {
                this.classList.add('incorrect');
            }
        });
    });
});