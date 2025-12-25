"""
Selenium реализация браузерной автоматизации.
Используется как fallback для совместимости.
"""
import logging
from typing import Optional, Dict, Any, List
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import undetected_chromedriver as uc
from .base_browser import BaseBrowserAutomation

logger = logging.getLogger(__name__)


class SeleniumAutomation(BaseBrowserAutomation):
    """
    Реализация браузерной автоматизации через Selenium.
    Использует undetected-chromedriver для обхода детекции.
    """
    
    def __init__(self, headless: bool = None, timeout: int = None, retry_count: int = None):
        super().__init__(headless, timeout, retry_count)
        self.driver: Optional[webdriver.Chrome] = None
    
    def start_browser(self) -> bool:
        """Запускает браузер через Selenium с undetected-chromedriver."""
        try:
            options = Options()
            if self.headless:
                options.add_argument('--headless')

            # undetected-chromedriver сам обрабатывает маскировку, не нужно дополнительных опций
            # Он автоматически скрывает признаки автоматизации

            # Используем Chrome из PATH или установленный в системе
            try:
                self.driver = uc.Chrome(options=options, version_main=None)
            except Exception as chrome_error:
                logger.warning(f"Не удалось запустить undetected-chromedriver: {chrome_error}")
                logger.info("🔄 Попытка с обычным Selenium ChromeDriver...")

                # Fallback: обычный ChromeDriver
                from selenium.webdriver.chrome.service import Service
                from webdriver_manager.chrome import ChromeDriverManager

                service = Service(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=options)
                logger.info("✅ Обычный ChromeDriver запущен")

            logger.info("🛡️ undetected-chromedriver успешно запущен")
            logger.info("🛡️ Автоматическая маскировка под обычный браузер активна")
            return True
        except Exception as e:
            logger.error(f"Ошибка запуска Selenium браузера: {e}", exc_info=True)
            return False
    
    def close_browser(self) -> None:
        """Закрывает браузер и освобождает ресурсы."""
        try:
            if self.driver:
                self.driver.quit()
            logger.info("Selenium браузер закрыт")
        except Exception as e:
            logger.error(f"Ошибка закрытия браузера: {e}", exc_info=True)
        finally:
            self.driver = None
    
    def navigate(self, url: str) -> bool:
        """Переходит по указанному URL."""
        try:
            if not self.driver:
                raise Exception("Браузер не запущен")
            self.driver.get(url)
            WebDriverWait(self.driver, self.timeout).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )
            logger.debug(f"Переход на {url} выполнен")
            return True
        except Exception as e:
            logger.error(f"Ошибка перехода на {url}: {e}", exc_info=True)
            return False
    
    def wait_for_element(
        self,
        selector: str,
        timeout: int = None,
        visible: bool = True
    ) -> Optional[Any]:
        """Ожидает появления элемента на странице."""
        try:
            if not self.driver:
                raise Exception("Браузер не запущен")
            wait = WebDriverWait(self.driver, timeout or self.timeout)
            if visible:
                element = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, selector)))
            else:
                element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
            return element
        except (TimeoutException, NoSuchElementException) as e:
            logger.warning(f"Элемент {selector} не найден: {e}")
            return None
    
    def click(self, selector: str, wait_timeout: int = None) -> bool:
        """Кликает по элементу."""
        try:
            element = self.wait_for_element(selector, wait_timeout)
            if element:
                element.click()
                self.random_delay()
                logger.debug(f"Клик по {selector} выполнен")
                return True
            return False
        except Exception as e:
            logger.error(f"Ошибка клика по {selector}: {e}", exc_info=True)
            return False
    
    def fill(self, selector: str, text: str, wait_timeout: int = None) -> bool:
        """Заполняет поле ввода текстом."""
        try:
            element = self.wait_for_element(selector, wait_timeout)
            if element:
                element.clear()
                element.send_keys(text)
                self.random_delay()
                logger.debug(f"Поле {selector} заполнено")
                return True
            return False
        except Exception as e:
            logger.error(f"Ошибка заполнения {selector}: {e}", exc_info=True)
            return False
    
    def upload_file(self, selector: str, file_path: str, wait_timeout: int = None) -> bool:
        """Загружает файл через input[type=file]."""
        try:
            element = self.wait_for_element(selector, wait_timeout)
            if element:
                element.send_keys(file_path)
                self.random_delay(1.0, 3.0)
                logger.debug(f"Файл {file_path} загружен через {selector}")
                return True
            return False
        except Exception as e:
            logger.error(f"Ошибка загрузки файла {file_path}: {e}", exc_info=True)
            return False
    
    def get_cookies(self) -> List[Dict[str, Any]]:
        """Получает все cookies из текущей сессии."""
        try:
            if self.driver:
                return self.driver.get_cookies()
            return []
        except Exception as e:
            logger.error(f"Ошибка получения cookies: {e}", exc_info=True)
            return []
    
    def set_cookies(self, cookies: List[Dict[str, Any]]) -> bool:
        """Устанавливает cookies в браузер."""
        try:
            if self.driver:
                # Сначала нужно перейти на домен, чтобы установить cookies
                if cookies:
                    domain = cookies[0].get('domain', '')
                    if domain:
                        self.driver.get(f"https://{domain}")
                for cookie in cookies:
                    try:
                        self.driver.add_cookie(cookie)
                    except Exception as e:
                        logger.warning(f"Не удалось установить cookie: {e}")
                logger.debug(f"Установлено {len(cookies)} cookies")
                return True
            return False
        except Exception as e:
            logger.error(f"Ошибка установки cookies: {e}", exc_info=True)
            return False
    
    def get_page_source(self) -> str:
        """Получает исходный код страницы."""
        try:
            if self.driver:
                return self.driver.page_source
            return ""
        except Exception as e:
            logger.error(f"Ошибка получения исходного кода: {e}", exc_info=True)
            return ""


