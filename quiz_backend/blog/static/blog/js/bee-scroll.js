async function initBee() {
  // Проверка поддержки WebGL перед загрузкой тяжелых библиотек
  function isWebGLAvailable() {
    try {
      const canvas = document.createElement('canvas');
      return !!(window.WebGLRenderingContext && (canvas.getContext('webgl') || canvas.getContext('experimental-webgl')));
    } catch (e) {
      return false;
    }
  }

  if (!isWebGLAvailable()) {
    console.warn("WebGL not supported, bee animation disabled");
    return;
  }

  // Динамический импорт библиотек
  console.log("Loading Three.js and GLTFLoader...");
  const THREE = await import("https://cdn.skypack.dev/three@0.129.0/build/three.module.js");
  const { GLTFLoader } = await import("https://cdn.skypack.dev/three@0.129.0/examples/jsm/loaders/GLTFLoader.js");
  console.log("Libraries loaded successfully");

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
  // Устанавливаем размер в зависимости от устройства
  const isMobileDevice = window.innerWidth <= 580;
  const initialSize = isMobileDevice ? 400 : 500;
  renderer.setSize(initialSize, initialSize);
  renderer.setClearColor(0x000000, 0); // Прозрачный фон
  // Сразу устанавливаем прозрачность canvas
  renderer.domElement.style.background = 'transparent';
  renderer.domElement.style.border = 'none';
  renderer.domElement.style.boxShadow = 'none';
  const container = document.getElementById("bee-container");
  if (container) {
    // Скрываем контейнер до загрузки модели и обеспечиваем прозрачность
    container.style.opacity = '0';
    container.style.background = 'transparent';
    container.style.border = 'none';
    container.style.boxShadow = 'none';
    container.appendChild(renderer.domElement);
    // Убеждаемся, что canvas тоже прозрачный
    renderer.domElement.style.background = 'transparent';
    renderer.domElement.style.border = 'none';
    renderer.domElement.style.boxShadow = 'none';
    console.log("Renderer appended to #bee-container, size:", initialSize + "px");
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
        // Проверяем, что данные валидны перед парсингом
        if (typeof savedPosition !== 'string' || !savedPosition.trim().startsWith('{')) {
          console.warn("Invalid bee position data in localStorage, clearing it");
          localStorage.removeItem('beePosition');
          return;
        }
        const position = JSON.parse(savedPosition);
        if (position && position.position && position.rotation) {
          bee.position.set(position.position.x, position.position.y, position.position.z);
          bee.rotation.set(position.rotation.x, position.rotation.y, position.rotation.z);
          console.log("Bee position restored from localStorage");
        }
      } catch (e) {
        console.warn("Error restoring bee position, clearing invalid data:", e);
        localStorage.removeItem('beePosition');
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
        // Проверяем, что данные валидны перед парсингом
        if (typeof savedPosition !== 'string' || !savedPosition.trim().startsWith('{')) {
          console.warn("Invalid bee position data in localStorage, clearing it");
          localStorage.removeItem('beePosition');
          return;
        }
        const position = JSON.parse(savedPosition);
        if (position && position.position && position.rotation) {
          bee.position.set(position.position.x, position.position.y, position.position.z);
          bee.rotation.set(position.rotation.x, position.rotation.y, position.rotation.z);
          // Восстанавливаем масштаб, если он был сохранен
          if (position.scale) {
            bee.scale.set(position.scale.x, position.scale.y, position.scale.z);
          }
        }
        console.log("Bee position and scale restored from localStorage:", position);
        return; // Выходим, если восстановили сохраненную позицию
      } catch (e) {
        console.warn("Error restoring bee position, clearing invalid data:", e);
        localStorage.removeItem('beePosition');
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
    "/static/blog/assets/bee.glb",
    function (gltf) {
      console.log("✅ Bee model loaded successfully");
      bee = gltf.scene;
      scene.add(bee);
      
      // Проверяем версию пчелы и очищаем старые данные
      const isMobile = window.innerWidth <= 580;
      const savedDeviceType = localStorage.getItem('beeDeviceType');
      const currentDeviceType = isMobile ? 'mobile' : 'desktop';
      const savedVersion = localStorage.getItem('beeScaleVersion');
      const currentVersion = 'v2.2'; // Новая версия для уменьшения размера на десктопе
      
      if (savedDeviceType && savedDeviceType !== currentDeviceType) {
        // Устройство изменилось, очищаем сохраненную позицию и масштаб
        localStorage.removeItem('beePosition');
        console.log("Device type changed from", savedDeviceType, "to", currentDeviceType, "- cleared saved data");
      }
      
      if (savedVersion !== currentVersion) {
        // Версия изменилась, очищаем сохраненные данные для применения новых размеров
        localStorage.removeItem('beePosition');
        localStorage.setItem('beeScaleVersion', currentVersion);
        console.log("Bee scale version updated to", currentVersion, "- cleared saved data");
      }
      
      localStorage.setItem('beeDeviceType', currentDeviceType);
      
      // Устанавливаем масштаб в зависимости от ширины экрана
      // Уменьшен размер пчелы для десктопа
      const scale = isMobile ? 0.25 : 0.26; // Уменьшили размер пчелы на десктопе
      bee.scale.set(scale, scale, scale);
      console.log("✅ Bee scale set to:", scale, "isMobile:", isMobile);
      
      // Устанавливаем позицию на основе текущего скролла или сохраненной позиции
      setInitialBeePosition();
      console.log("✅ Bee position set");
      
      // Сохраняем начальную позицию и масштаб
      setTimeout(() => {
        saveBeePosition();
      }, 100);
      
      console.log("✅ Bee model added to scene");

          mixer = new THREE.AnimationMixer(bee);
      mixer.clipAction(gltf.animations[0]).play();
      console.log("✅ Bee animation started");

      // Плавно показываем контейнер после загрузки модели
      setTimeout(() => {
        if (container) {
          console.log("🔍 Showing bee container...");
          console.log("🔍 Container current opacity:", container.style.opacity);
          // Убеждаемся в прозрачности фона перед показом
          container.style.background = 'transparent';
          renderer.domElement.style.background = 'transparent';
          // Показываем контейнер
          container.style.opacity = '1';
          console.log("✅ Bee container shown, opacity set to 1");
          console.log("🔍 Container new opacity:", container.style.opacity);
        } else {
          console.error("❌ Container not found when trying to show bee");
        }
      }, 200); // Уменьшил задержку

      // Настройка анимации скролла
      setupScrollAnimation(THREE, bee);
    },
    function (xhr) {
      console.log("Model loading: " + (xhr.loaded / xhr.total) * 100 + "%");
    },
    function (error) {
      console.error("Error loading model:", error);
    }
  );

  // Анимация и рендер
  let animationStarted = false;
  const animate = () => {
    requestAnimationFrame(animate);
    
    // Первый кадр - убеждаемся в прозрачности
    if (!animationStarted) {
      renderer.domElement.style.background = 'transparent';
      animationStarted = true;
    }
    
    if (mixer) mixer.update(0.02);
    renderer.render(scene, camera);
  };
  animate();

  // Адаптация при изменении размера
  window.addEventListener("resize", () => {
    const container = document.getElementById("bee-container");
    if (container) {
      // Обновляем позицию и размер контейнера
      updateContainerPosition();
      
      // Обновляем размер рендерера
      const isMobile = window.innerWidth <= 580;
      const size = isMobile ? 400 : 500;
      renderer.setSize(size, size);
      camera.aspect = 1; // Всегда квадратный
      camera.updateProjectionMatrix();
      
      // НЕ изменяем масштаб пчелы при resize, оставляем как было установлено изначально
      console.log("Container resized, size:", size + "px", "bee scale preserved");
    }
  });

  // Функция для динамического позиционирования контейнера
  function updateContainerPosition() {
    const isMobile = window.innerWidth <= 580;
    const container = document.getElementById("bee-container");
    if (container) {
      // Обновляем только позицию, размеры остаются в CSS
      gsap.set(container, {
        left: isMobile ? "30%" : "70%" // Ближе к центру на мобильных
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
  function setupScrollAnimation(THREE, bee) {
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
}

// Запуск инициализации
initBee();