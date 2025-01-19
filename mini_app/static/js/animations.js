document.addEventListener('DOMContentLoaded', () => {
    // Matrix Rain
    const rainContainer = document.querySelector('.matrix-rain__container');
    
    function createDrop() {
        const drop = document.createElement('div');
        drop.classList.add('matrix-rain__drop');
        drop.innerHTML = Math.random() < 0.5 ? '1' : '0';
        drop.style.left = Math.random() * 100 + 'vw';
        drop.style.animationDuration = Math.random() * 2 + 's';
        rainContainer.appendChild(drop);
        
        setTimeout(() => {
            drop.remove();
        }, 2000);
    }
    
    // Создаем капли чаще для более плотного дождя
    setInterval(createDrop, 50);
    
    // Gallery rotation
    const gallery = document.querySelector('.matrix-gallery__container');
    let rotationAngle = 0;
    
    function rotateGallery() {
        rotationAngle += 0.5;
        gallery.style.transform = `rotateY(${rotationAngle}deg)`;
        requestAnimationFrame(rotateGallery);
    }
    
    rotateGallery();
});