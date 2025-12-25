"""
Playwright реализация браузерной автоматизации.
"""
import logging
from typing import Optional, Dict, Any, List
from playwright.sync_api import sync_playwright, Browser, Page, BrowserContext
from .base_browser import BaseBrowserAutomation

# Stealth plugin для обхода детекции автоматизации
try:
    from playwright_stealth import stealth_sync
    STEALTH_AVAILABLE = True
except ImportError:
    STEALTH_AVAILABLE = False

logger = logging.getLogger(__name__)


class PlaywrightAutomation(BaseBrowserAutomation):
    """
    Реализация браузерной автоматизации через Playwright.
    """
    
    def __init__(self, headless: bool = None, timeout: int = None, retry_count: int = None):
        super().__init__(headless, timeout, retry_count)
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
    
    def start_browser(self) -> bool:
        """
        Запускает браузер через Playwright.
        Использует self.mobile_mode для определения мобильного режима.
        """
        try:
            self.playwright = sync_playwright().start()

            # Расширенные аргументы для обхода детекции автоматизации
            browser_args = [
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--disable-extensions',
                '--disable-plugins',
                '--disable-default-apps',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding',
                '--disable-field-trial-config',
                '--disable-back-forward-cache',
                '--disable-hang-monitor',
                '--disable-ipc-flooding-protection',
                '--disable-popup-blocking',
                '--disable-prompt-on-repost',
                '--disable-component-update',
                '--disable-domain-reliability',
                '--disable-client-side-phishing-detection',
                '--disable-background-networking',
                '--no-default-browser-check',
                '--no-first-run',
                '--mute-audio',
                '--disable-sync',
                '--disable-translate',
                '--hide-scrollbars',
                '--metrics-recording-only',
                '--no-crash-upload',
                '--disable-gpu',
                '--disable-software-rasterizer',
                '--disable-background-media-download',
                '--disable-print-preview',
                '--disable-component-extensions-with-background-pages'
            ]

            self.browser = self.playwright.chromium.launch(
                headless=self.headless,
                args=browser_args
            )
            
            if self.mobile_mode:
                # Мобильные настройки для Instagram Reels
                mobile_user_agent = 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'
                viewport = {'width': 390, 'height': 844}  # iPhone 12 Pro размеры
                device_scale_factor = 3
                logger.info("📱 Запуск браузера в мобильном режиме для Instagram Reels")
            else:
                # Десктопные настройки
                mobile_user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                viewport = {'width': 1920, 'height': 1080}
                device_scale_factor = None
            
            context_options = {
                'viewport': viewport,
                'user_agent': mobile_user_agent
            }
            if device_scale_factor:
                context_options['device_scale_factor'] = device_scale_factor
            
            self.context = self.browser.new_context(**context_options)
            self.page = self.context.new_page()

            # Применяем stealth plugin для обхода детекции автоматизации
            if STEALTH_AVAILABLE:
                try:
                    stealth_sync(self.page)
                    logger.info("🛡️ Stealth plugin применен - браузер замаскирован")
                except Exception as stealth_error:
                    logger.warning(f"⚠️ Ошибка применения stealth plugin: {stealth_error}")
            else:
                logger.info("ℹ️ playwright-stealth не установлен - используем базовую маскировку")
                # Альтернативная маскировка без stealth plugin
                try:
                    self.page.add_init_script("""
                        Object.defineProperty(navigator, 'webdriver', {
                            get: () => undefined,
                        });
                    """)
                    logger.info("🛡️ Базовая маскировка автоматизации применена")
                except Exception as mask_error:
                    logger.warning(f"⚠️ Ошибка базовой маскировки: {mask_error}")

            logger.info("Playwright браузер успешно запущен")
            return True
        except Exception as e:
            logger.error(f"Ошибка запуска Playwright браузера: {e}", exc_info=True)
            return False
    
    def close_browser(self) -> None:
        """Закрывает браузер и освобождает ресурсы."""
        try:
            if self.page:
                self.page.close()
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
            logger.info("Playwright браузер закрыт")
        except Exception as e:
            logger.error(f"Ошибка закрытия браузера: {e}", exc_info=True)
        finally:
            self.page = None
            self.context = None
            self.browser = None
            self.playwright = None
    
    def navigate(self, url: str) -> bool:
        """Переходит по указанному URL."""
        try:
            if not self.page:
                raise Exception("Браузер не запущен")
            self.page.goto(url, wait_until='networkidle', timeout=self.timeout * 1000)
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
            if not self.page:
                raise Exception("Браузер не запущен")
            timeout_ms = (timeout or self.timeout) * 1000
            if visible:
                self.page.wait_for_selector(selector, state='visible', timeout=timeout_ms)
            else:
                self.page.wait_for_selector(selector, timeout=timeout_ms)
            element = self.page.locator(selector).first
            return element
        except Exception as e:
            logger.warning(f"Элемент {selector} не найден: {e}")
            return None
    
    def click(self, selector: str, wait_timeout: int = None) -> bool:
        """Кликает по элементу."""
        try:
            element = self.wait_for_element(selector, wait_timeout)
            if element:
                element.click(timeout=(wait_timeout or self.timeout) * 1000)
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
                element.fill(text, timeout=(wait_timeout or self.timeout) * 1000)
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
            timeout_ms = (wait_timeout or self.timeout) * 1000
            
            # Пробуем найти элемент (может быть скрыт)
            try:
                element = self.wait_for_element(selector, wait_timeout, visible=False)
            except:
                # Если не нашли через wait_for_element, пробуем через query_selector
                try:
                    if self.page:
                        element = self.page.query_selector(selector)
                    else:
                        element = None
                except:
                    element = None
            
            if element:
                try:
                    element.set_input_files(file_path, timeout=timeout_ms)
                    self.random_delay(1.0, 3.0)
                    logger.info(f"✅ Файл {file_path} загружен через {selector}")
                    return True
                except Exception as upload_error:
                    logger.warning(f"Не удалось загрузить через set_input_files: {upload_error}")
                    # Пробуем альтернативный способ - через JavaScript
                    try:
                        if self.page:
                            # Используем evaluate для прямой загрузки
                            with open(file_path, 'rb') as f:
                                file_content = f.read()
                            
                            # Альтернатива - просто пробуем еще раз с большим таймаутом
                            element.set_input_files(file_path, timeout=30000)
                            self.random_delay(1.0, 3.0)
                            logger.info(f"✅ Файл загружен (вторая попытка)")
                            return True
                    except Exception as e2:
                        logger.error(f"Альтернативный способ тоже не сработал: {e2}")
            
            return False
        except Exception as e:
            logger.error(f"Ошибка загрузки файла {file_path}: {e}", exc_info=True)
            return False
    
    def get_cookies(self) -> List[Dict[str, Any]]:
        """Получает все cookies из текущей сессии."""
        try:
            if self.context:
                return self.context.cookies()
            return []
        except Exception as e:
            logger.error(f"Ошибка получения cookies: {e}", exc_info=True)
            return []
    
    def set_cookies(self, cookies: List[Dict[str, Any]]) -> bool:
        """Устанавливает cookies в браузер."""
        try:
            if self.context:
                self.context.add_cookies(cookies)
                logger.debug(f"Установлено {len(cookies)} cookies")
                return True
            return False
        except Exception as e:
            logger.error(f"Ошибка установки cookies: {e}", exc_info=True)
            return False
    
    def get_page_source(self) -> str:
        """Получает исходный код страницы."""
        try:
            if self.page:
                return self.page.content()
            return ""
        except Exception as e:
            logger.error(f"Ошибка получения исходного кода: {e}", exc_info=True)
            return ""
    
    def get_current_url(self) -> Optional[str]:
        """Возвращает текущий URL страницы."""
        try:
            if self.page:
                return self.page.url
            return None
        except Exception as e:
            logger.error(f"Ошибка получения текущего URL: {e}", exc_info=True)
            return None
    
    def wait_for_upload_complete(self, timeout: int = 300) -> bool:
        """
        Ожидает завершения загрузки файла.
        Проверяет наличие индикаторов загрузки на странице.
        """
        try:
            if not self.page:
                return False
            
            # Ждем исчезновения индикаторов загрузки
            selectors_to_wait = [
                '[aria-label*="Upload"]',
                '[aria-label*="upload"]',
                '.upload-progress',
                '[data-testid*="upload"]',
            ]
            
            for selector in selectors_to_wait:
                try:
                    self.page.wait_for_selector(
                        selector,
                        state='hidden',
                        timeout=timeout * 1000
                    )
                except:
                    pass  # Игнорируем, если селектор не найден
            
            # Дополнительная задержка для завершения обработки
            self.random_delay(2.0, 4.0)
            return True
        except Exception as e:
            logger.warning(f"Ошибка ожидания загрузки: {e}")
            return False


