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
const renderer = new THREE.WebGLRenderer({ 
  alpha: true,
  antialias: true,
  premultipliedAlpha: false
});
renderer.setSize(600, 600);
renderer.setClearColor(0x000000, 0); // Прозрачный фон
const container = document.getElementById("bee-container");
if (container) {
  // Скрываем контейнер до загрузки модели
  container.style.opacity = '0';
  container.appendChild(renderer.domElement);
  // Убеждаемся, что canvas тоже прозрачный
  renderer.domElement.style.background = 'transparent';
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

// Функция для сохранения позиции и масштаба пчелы
function saveBeePosition() {
  if (bee) {
    const position = {
      position: { x: bee.position.x, y: bee.position.y, z: bee.position.z },
      rotation: { x: bee.rotation.x, y: bee.rotation.y, z: bee.rotation.z },
      scale: { x: bee.scale.x, y: bee.scale.y, z: bee.scale.z }
    };
    localStorage.setItem('beePosition', JSON.stringify(position));
  }
}

// Функция для восстановления позиции пчелы
function restoreBeePosition() {
  const savedPosition = localStorage.getItem('beePosition');
  if (savedPosition && bee) {
    try {
      const position = JSON.parse(savedPosition);
      bee.position.set(position.position.x, position.position.y, position.position.z);
      bee.rotation.set(position.rotation.x, position.rotation.y, position.rotation.z);
      console.log("Bee position restored from localStorage");
    } catch (e) {
      console.error("Error restoring bee position:", e);
    }
  }
}

// Функция для установки начальной позиции на основе текущего скролла
function setInitialBeePosition() {
  if (!bee) return;
  
  // Сначала пытаемся восстановить сохраненную позицию
  const savedPosition = localStorage.getItem('beePosition');
  if (savedPosition) {
    try {
      const position = JSON.parse(savedPosition);
      bee.position.set(position.position.x, position.position.y, position.position.z);
      bee.rotation.set(position.rotation.x, position.rotation.y, position.rotation.z);
      // Восстанавливаем масштаб, если он был сохранен
      if (position.scale) {
        bee.scale.set(position.scale.x, position.scale.y, position.scale.z);
      }
      console.log("Bee position and scale restored from localStorage:", position);
      return; // Выходим, если восстановили сохраненную позицию
    } catch (e) {
      console.error("Error restoring bee position:", e);
    }
  }
  
  // Если нет сохраненной позиции, устанавливаем на основе скролла
  const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
  const documentHeight = document.documentElement.scrollHeight - window.innerHeight;
  const scrollPercent = documentHeight > 0 ? Math.min((scrollTop / documentHeight) * 100, 100) : 0;
  
  // Находим подходящую позицию на основе процента скролла
  const scrollPositions = getScrollPositions();
  let targetPosition = scrollPositions[0];
  for (let i = 0; i < scrollPositions.length; i++) {
    if (scrollPercent >= scrollPositions[i].scrollPercent) {
      targetPosition = scrollPositions[i];
    } else {
      break;
    }
  }
  
  // Устанавливаем позицию без анимации
  const direction = scrollTop > 0 ? "down" : "up";
  const coords = targetPosition[direction];
  bee.position.set(coords.position.x, coords.position.y, coords.position.z);
  bee.rotation.set(coords.rotation.x, coords.rotation.y, coords.rotation.z);
  console.log("Bee position set based on scroll:", coords, "scrollPercent:", scrollPercent);
}

loader.load(
  "/static/assets/bee.glb",
  function (gltf) {
    bee = gltf.scene;
    scene.add(bee);
    
    // Проверяем, изменился ли тип устройства и очищаем сохраненные данные если нужно
    const isMobile = window.innerWidth <= 580;
    const savedDeviceType = localStorage.getItem('beeDeviceType');
    const currentDeviceType = isMobile ? 'mobile' : 'desktop';
    
    if (savedDeviceType && savedDeviceType !== currentDeviceType) {
      // Устройство изменилось, очищаем сохраненную позицию
      localStorage.removeItem('beePosition');
      console.log("Device type changed, cleared saved position");
    }
    localStorage.setItem('beeDeviceType', currentDeviceType);
    
    // Устанавливаем масштаб в зависимости от ширины экрана
    const scale = isMobile ? 0.2 : 0.3; // Меньше на мобильных
    bee.scale.set(scale, scale, scale);
    console.log("Bee scale set to:", scale, "isMobile:", isMobile);
    
    // Устанавливаем позицию на основе текущего скролла или сохраненной позиции
    setInitialBeePosition();
    
    // Сохраняем начальную позицию и масштаб
    setTimeout(() => {
      saveBeePosition();
    }, 100);
    
    console.log("Bee model added to scene");

    mixer = new THREE.AnimationMixer(bee);
    mixer.clipAction(gltf.animations[0]).play();
    console.log("Bee animation started");

    // Плавно показываем контейнер после загрузки модели
    setTimeout(() => {
      if (container) {
        container.style.transition = 'opacity 0.5s ease-in-out';
        container.style.opacity = '1';
      }
    }, 100);

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
    // НЕ изменяем масштаб пчелы при resize, оставляем как было установлено изначально
    console.log("Container resized, but bee scale preserved");
  }
});

// Функция для динамического позиционирования контейнера
function updateContainerPosition() {
  const isMobile = window.innerWidth <= 580;
  const container = document.getElementById("bee-container");
  if (container) {
    gsap.set(container, {
      position: "fixed",
      top: "60%",
      left: isMobile ? "30%" : "70%", // Ещё ближе к центру на мобильных
      transform: "translate(-50%, -50%)",
      zIndex: 999 // z-index для отображения поверх контента
    });
    console.log("Container position updated:", "isMobile:", isMobile, "left:", isMobile ? "30%" : "70%");
  }
}

// Функция для получения позиций скролла
function getScrollPositions() {
  return [
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
}

// Универсальная анимация скролла для всех страниц
function setupScrollAnimation() {
  console.log("Setting up universal scroll animation");
  gsap.registerPlugin(ScrollTrigger);

  // Начальная позиция контейнера
  updateContainerPosition();

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
    const scrollPositions = getScrollPositions();
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
  let scrollTimeout;
  window.addEventListener("scroll", () => {
    if (bee) {
      modelMove();
      
      // Сохраняем позицию через небольшую задержку после окончания скролла
      clearTimeout(scrollTimeout);
      scrollTimeout = setTimeout(() => {
        saveBeePosition();
      }, 100);
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