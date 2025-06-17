import * as THREE from "https://cdn.skypack.dev/three@0.129.0/build/three.module.js";
import { GLTFLoader } from "https://cdn.skypack.dev/three@0.129.0/examples/jsm/loaders/GLTFLoader.js";

// Настройка сцены
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(
  20,
  600 / 600,
  0.1,
  1000
);
camera.position.z = 5;
camera.lookAt(0, 0, 0);

// Рендерер
const renderer = new THREE.WebGLRenderer({ alpha: true });
renderer.setSize(600, 600);
const container = document.getElementById("bee-container");
if (container) {
  container.appendChild(renderer.domElement);
  console.log("Renderer appended to #bee-container");
} else {
  console.error("Container #bee-container not found");
}

// Освещение
const ambientLight = new THREE.AmbientLight(0xffffff, 1.5);
scene.add(ambientLight);
const topLight = new THREE.DirectionalLight(0xffffff, 1);
topLight.position.set(500, 500, 500);
scene.add(topLight);

// Загрузка модели
let bee;
let mixer;
const loader = new GLTFLoader();
loader.load(
  "/static/assets/bee.glb",
  function (gltf) {
    bee = gltf.scene;
    scene.add(bee);
    // Устанавливаем масштаб в зависимости от ширины экрана
    const isMobile = window.innerWidth <= 580;
    const scale = isMobile ? 0.2 : 0.3; // Меньше на мобильных
    bee.scale.set(scale, scale, scale);
    console.log("Bee scale set to:", scale, "isMobile:", isMobile);
    bee.position.set(0, -0.5, 0); // Центр контейнера
    bee.rotation.set(0, 1.5, 0);
    console.log("Bee model added to scene");

    mixer = new THREE.AnimationMixer(bee);
    mixer.clipAction(gltf.animations[0]).play();
    console.log("Bee animation started");

    // Настройка анимации скролла
    setupScrollAnimation();
  },
  function (xhr) {
    console.log("Model loading: " + (xhr.loaded / xhr.total) * 100 + "%");
  },
  function (error) {
    console.error("Error loading model:", error);
  }
);

// Анимация и рендер
const animate = () => {
  requestAnimationFrame(animate);
  if (mixer) mixer.update(0.02);
  renderer.render(scene, camera);
};
animate();

// Адаптация при изменении размера
window.addEventListener("resize", () => {
  const container = document.getElementById("bee-container");
  if (container) {
    renderer.setSize(container.clientWidth, container.clientHeight);
    camera.aspect = container.clientWidth / container.clientHeight;
    camera.updateProjectionMatrix();
    // Обновляем позицию контейнера
    updateContainerPosition();
    // Обновляем масштаб пчелы
    const isMobile = window.innerWidth <= 580;
    const scale = isMobile ? 0.2 : 0.3;
    if (bee) {
      bee.scale.set(scale, scale, scale);
      console.log("Bee scale updated on resize:", scale, "isMobile:", isMobile);
    }
  }
});

// Функция для динамического позиционирования контейнера
function updateContainerPosition() {
  const isMobile = window.innerWidth <= 580;
  gsap.set("#bee-container", {
    position: "fixed",
    top: "60%",
    left: isMobile ? "30%" : "70%", // Ещё ближе к центру на мобильных
    transform: "translate(-50%, -50%)",
    zIndex: 1000 // Добавляем z-index для отображения поверх контента
  });
  console.log("Container position updated:", "isMobile:", isMobile, "left:", isMobile ? "30%" : "70%");
}

// Универсальная анимация скролла для всех страниц
function setupScrollAnimation() {
  console.log("Setting up universal scroll animation");
  gsap.registerPlugin(ScrollTrigger);

  // Начальная позиция контейнера
  updateContainerPosition();

  // Универсальные позиции для разных этапов скролла
  const scrollPositions = [
    {
      scrollPercent: 0,
      down: { position: { x: 0, y: -0.5, z: 0 }, rotation: { x: 0, y: 1.5, z: 0 } },
      up: { position: { x: 0, y: -0.5, z: 0 }, rotation: { x: 0, y: -1.5, z: 0 } }
    },
    {
      scrollPercent: 25,
      down: { position: { x: 0.2, y: -0.4, z: -0.1 }, rotation: { x: 0.02, y: 0.5, z: 0.01 } },
      up: { position: { x: -0.2, y: -0.6, z: 0.1 }, rotation: { x: -0.02, y: 2.5, z: -0.01 } }
    },
    {
      scrollPercent: 50,
      down: { position: { x: 0.3, y: -0.6, z: -0.1 }, rotation: { x: 0.03, y: -0.5, z: 0.02 } },
      up: { position: { x: -0.3, y: -0.3, z: 0 }, rotation: { x: -0.03, y: 0.5, z: -0.02 } }
    },
    {
      scrollPercent: 75,
      down: { position: { x: -0.1, y: -0.7, z: -0.2 }, rotation: { x: 0.01, y: 1.0, z: -0.01 } },
      up: { position: { x: 0.1, y: -0.3, z: 0.1 }, rotation: { x: -0.01, y: -1.0, z: 0.01 } }
    },
    {
      scrollPercent: 100,
      down: { position: { x: -0.3, y: -0.7, z: -0.2 }, rotation: { x: 0, y: 0.5, z: -0.02 } },
      up: { position: { x: 0.3, y: -0.4, z: 0 }, rotation: { x: 0, y: -0.5, z: 0.02 } }
    }
  ];

  // Отслеживание направления скролла
  let lastScrollTop = 0;
  let scrollDirection = "down";

  // Функция движения пчелы на основе процента скролла
  const modelMove = () => {
    // Вычисляем процент скролла страницы
    const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
    const documentHeight = document.documentElement.scrollHeight - window.innerHeight;
    const scrollPercent = documentHeight > 0 ? Math.min((scrollTop / documentHeight) * 100, 100) : 0;

    // Определяем направление скролла
    scrollDirection = scrollTop > lastScrollTop ? "down" : "up";
    lastScrollTop = scrollTop <= 0 ? 0 : scrollTop;

    // Находим подходящую позицию на основе процента скролла
    let targetPosition = scrollPositions[0];
    for (let i = 0; i < scrollPositions.length; i++) {
      if (scrollPercent >= scrollPositions[i].scrollPercent) {
        targetPosition = scrollPositions[i];
      } else {
        break;
      }
    }

    if (bee && targetPosition) {
      let newCoordinates = targetPosition[scrollDirection];
      gsap.to(bee.position, {
        x: newCoordinates.position.x,
        y: newCoordinates.position.y,
        z: newCoordinates.position.z,
        duration: 2,
        ease: "power1.out"
      });
      gsap.to(bee.rotation, {
        x: newCoordinates.rotation.x,
        y: newCoordinates.rotation.y,
        z: newCoordinates.rotation.z,
        duration: 2,
        ease: "power1.out"
      });
    }
  };

  // Запуск движения при скролле
  window.addEventListener("scroll", () => {
    if (bee) {
      modelMove();
    }
  });

  // Добавляем плавное движение пчелы при простое (idle анимация)
  setInterval(() => {
    if (bee && lastScrollTop === (window.pageYOffset || document.documentElement.scrollTop)) {
      // Если пользователь не скроллит, добавляем легкое покачивание
      gsap.to(bee.rotation, {
        y: bee.rotation.y + 0.1,
        duration: 3,
        ease: "sine.inOut",
        yoyo: true,
        repeat: 1
      });
    }
  }, 5000); // Каждые 5 секунд
}