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
    transform: "translate(-50%, -50%)"
  });
  console.log("Container position updated:", "isMobile:", isMobile, "left:", isMobile ? "30%" : "70%");
}

// Анимация скролла
function setupScrollAnimation() {
  console.log("Setting up scroll animation");
  gsap.registerPlugin(ScrollTrigger);

  // Начальная позиция контейнера
  updateContainerPosition();

  // Массив позиций для разных секций и направлений скролла
  const arrPositionModel = [
    {
      id: "filter-list",
      down: { position: { x: 0, y: -0.5, z: 0 }, rotation: { x: 0, y: 1.5, z: 0 } },
      up: { position: { x: 0, y: -0.5, z: 0 }, rotation: { x: 0, y: -1.5, z: 0 } }
    },
    {
      id: "blog-posts-list",
      down: { position: { x: 0.3, y: -0.6, z: -0.1 }, rotation: { x: 0.03, y: -0.5, z: 0.02 } },
      up: { position: { x: -0.3, y: -0.3, z: 0 }, rotation: { x: -0.03, y: 0.5, z: -0.02 } }
    },
    {
      id: "pagination",
      down: { position: { x: -0.3, y: -0.7, z: -0.2 }, rotation: { x: 0, y: 0.5, z: -0.02 } },
      up: { position: { x: 0.3, y: -0.4, z: 0 }, rotation: { x: 0, y: -0.5, z: 0.02 } }
    }
  ];

  // Отслеживание направления скролла
  let lastScrollTop = 0;
  let scrollDirection = "down";

  // Функция движения пчелы
  const modelMove = () => {
    const sections = document.querySelectorAll(".filter-list, .blog-posts-list, .pagination");
    let currentSection;
    sections.forEach((section) => {
      const rect = section.getBoundingClientRect();
      if (rect.top <= window.innerHeight / 2) {
        currentSection = section.className.split(" ")[0];
      }
    });

    // Определяем направление скролла
    const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
    scrollDirection = scrollTop > lastScrollTop ? "down" : "up";
    lastScrollTop = scrollTop <= 0 ? 0 : scrollTop;

    let position_active = arrPositionModel.findIndex(
      (val) => val.id === currentSection
    );
    if (position_active >= 0 && bee) {
      let new_coordinates = arrPositionModel[position_active][scrollDirection];
      gsap.to(bee.position, {
        x: new_coordinates.position.x,
        y: new_coordinates.position.y,
        z: new_coordinates.position.z,
        duration: 3,
        ease: "power1.out"
      });
      gsap.to(bee.rotation, {
        x: new_coordinates.rotation.x,
        y: new_coordinates.rotation.y,
        z: new_coordinates.rotation.z,
        duration: 3,
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
}