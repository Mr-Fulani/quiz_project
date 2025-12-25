"""
Базовый класс для браузерной автоматизации.
Предоставляет общие методы для работы с браузером через Playwright и Selenium.
"""
import logging
import time
import random
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from django.conf import settings

logger = logging.getLogger(__name__)


class BaseBrowserAutomation(ABC):
    """
    Абстрактный базовый класс для браузерной автоматизации.
    Предоставляет общие методы и интерфейс для работы с браузерами.
    """
    
    def __init__(
        self,
        headless: bool = None,
        timeout: int = None,
        retry_count: int = None
    ):
        """
        Инициализация браузерной автоматизации.
        
        Args:
            headless: Режим без интерфейса (по умолчанию из settings)
            timeout: Таймаут операций в секундах (по умолчанию из settings)
            retry_count: Количество повторных попыток (по умолчанию из settings)
        """
        self.headless = headless if headless is not None else getattr(
            settings, 'BROWSER_HEADLESS', True
        )
        self.timeout = timeout or getattr(settings, 'BROWSER_TIMEOUT', 60)
        self.retry_count = retry_count or getattr(settings, 'BROWSER_RETRY_COUNT', 3)
        self.browser = None
        self.page = None
        
    @abstractmethod
    def start_browser(self) -> bool:
        """
        Запускает браузер.
        
        Returns:
            bool: True если браузер успешно запущен
        """
        pass
    
    @abstractmethod
    def close_browser(self) -> None:
        """Закрывает браузер и освобождает ресурсы."""
        pass
    
    @abstractmethod
    def navigate(self, url: str) -> bool:
        """
        Переходит по указанному URL.
        
        Args:
            url: URL для перехода
            
        Returns:
            bool: True если переход успешен
        """
        pass
    
    @abstractmethod
    def wait_for_element(
        self,
        selector: str,
        timeout: int = None,
        visible: bool = True
    ) -> Optional[Any]:
        """
        Ожидает появления элемента на странице.
        
        Args:
            selector: CSS селектор или XPath
            timeout: Таймаут ожидания в секундах
            visible: Должен ли элемент быть видимым
            
        Returns:
            Элемент или None если не найден
        """
        pass
    
    @abstractmethod
    def click(self, selector: str, wait_timeout: int = None) -> bool:
        """
        Кликает по элементу.
        
        Args:
            selector: CSS селектор или XPath
            wait_timeout: Таймаут ожидания элемента
            
        Returns:
            bool: True если клик успешен
        """
        pass
    
    @abstractmethod
    def fill(self, selector: str, text: str, wait_timeout: int = None) -> bool:
        """
        Заполняет поле ввода текстом.
        
        Args:
            selector: CSS селектор или XPath
            text: Текст для ввода
            wait_timeout: Таймаут ожидания элемента
            
        Returns:
            bool: True если заполнение успешно
        """
        pass
    
    @abstractmethod
    def upload_file(self, selector: str, file_path: str, wait_timeout: int = None) -> bool:
        """
        Загружает файл через input[type=file].
        
        Args:
            selector: CSS селектор для input[type=file]
            file_path: Путь к файлу
            wait_timeout: Таймаут ожидания элемента
            
        Returns:
            bool: True если загрузка успешна
        """
        pass
    
    @abstractmethod
    def get_cookies(self) -> List[Dict[str, Any]]:
        """
        Получает все cookies из текущей сессии.
        
        Returns:
            List[Dict]: Список cookies
        """
        pass
    
    @abstractmethod
    def set_cookies(self, cookies: List[Dict[str, Any]]) -> bool:
        """
        Устанавливает cookies в браузер.
        
        Args:
            cookies: Список cookies для установки
            
        Returns:
            bool: True если установка успешна
        """
        pass
    
    @abstractmethod
    def get_page_source(self) -> str:
        """
        Получает исходный код страницы.
        
        Returns:
            str: HTML код страницы
        """
        pass
    
    def random_delay(self, min_seconds: float = 0.5, max_seconds: float = 2.0) -> None:
        """
        Случайная задержка для имитации человеческого поведения.
        
        Args:
            min_seconds: Минимальная задержка в секундах
            max_seconds: Максимальная задержка в секундах
        """
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)
    
    def safe_retry(self, func, *args, **kwargs):
        """
        Выполняет функцию с повторными попытками при ошибках.
        
        Args:
            func: Функция для выполнения
            *args: Позиционные аргументы
            **kwargs: Именованные аргументы
            
        Returns:
            Результат выполнения функции
            
        Raises:
            Exception: Если все попытки неудачны
        """
        last_exception = None
        
        for attempt in range(1, self.retry_count + 1):
            try:
                logger.debug(f"Попытка {attempt}/{self.retry_count}: {func.__name__}")
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                logger.warning(
                    f"Попытка {attempt}/{self.retry_count} неудачна: {e}. "
                    f"Повтор через {attempt * 2} секунд..."
                )
                if attempt < self.retry_count:
                    time.sleep(attempt * 2)
        
        logger.error(f"Все {self.retry_count} попыток неудачны для {func.__name__}")
        raise last_exception
    
    def __enter__(self):
        """Контекстный менеджер: запускает браузер."""
        self.start_browser()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Контекстный менеджер: закрывает браузер."""
        self.close_browser()


