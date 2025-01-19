document.addEventListener('DOMContentLoaded', () => {
    const gallery = document.querySelector('.gallery__container');
    let rotationAngle = 0;

    function rotateGallery() {
        rotationAngle += 0.5;
        gallery.style.transform = `perspective(1000px) rotateY(${rotationAngle}deg)`;
        requestAnimationFrame(rotateGallery);
    }

    rotateGallery();
}); 