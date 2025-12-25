"""
Автоматизация публикации в Instagram Reels через браузер.
Поддерживает одновременную публикацию в Facebook через чекбоксы.
"""
import logging
import os
import tempfile
import requests
import subprocess
import time
from typing import Dict, Optional, Any
from django.conf import settings
from django.utils import timezone

from ..base_browser import BaseBrowserAutomation
from ..playwright_service import PlaywrightAutomation
from ..selenium_service import SeleniumAutomation
from ..session_manager import BrowserSessionManager
from webhooks.models import SocialMediaCredentials

logger = logging.getLogger(__name__)


class InstagramReelsAutomation:
    """
    Автоматизация публикации в Instagram Reels.
    Поддерживает кросспостинг в Facebook через встроенные чекбоксы.
    """
    
    INSTAGRAM_URL = "https://www.instagram.com"
    # В десктопной версии Reels создаются через "Создать" -> "Публикация" -> выбор размера 9:16
    INSTAGRAM_REELS_UPLOAD_URL = "https://www.instagram.com"
    
    def __init__(
        self,
        credentials: SocialMediaCredentials,
        browser_type: str = 'playwright'
    ):
        """
        Инициализация Instagram Reels автоматизации.
        
        Args:
            credentials: Объект SocialMediaCredentials с данными Instagram
            browser_type: Тип браузера ('playwright' или 'selenium')
        """
        self.credentials = credentials
        self.browser_type = browser_type or credentials.browser_type or 'playwright'
        self.browser: Optional[BaseBrowserAutomation] = None
        self.session_manager = BrowserSessionManager()
    
    def _start_xvfb_if_needed(self) -> Optional[str]:
        """
        Запускает xvfb в Docker окружении, если нужно.
        Возвращает DISPLAY значение или None.
        """
        try:
            has_display = bool(os.environ.get('DISPLAY'))
            is_docker = os.path.exists('/.dockerenv') or os.environ.get('DOCKER_CONTAINER') == 'true'
            
            if has_display or not is_docker:
                return None  # XServer уже есть или не Docker
            
            # Проверяем, запущен ли уже xvfb
            try:
                result = subprocess.run(['pgrep', '-f', 'Xvfb'], capture_output=True, timeout=2)
                if result.returncode == 0:
                    # xvfb уже запущен
                    display_num = ':99'  # По умолчанию
                    if not os.environ.get('DISPLAY'):
                        os.environ['DISPLAY'] = display_num
                    return os.environ.get('DISPLAY')
            except (subprocess.TimeoutExpired, FileNotFoundError):
                # pgrep недоступен или завис - пропускаем проверку
                pass
            
            # Запускаем xvfb
            display_num = ':99'
            subprocess.Popen(
                ['Xvfb', display_num, '-screen', '0', '1920x1080x24', '-ac', '+extension', 'GLX'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            # Даем время на запуск
            time.sleep(1)
            os.environ['DISPLAY'] = display_num
            logger.info(f"✅ Запущен xvfb с DISPLAY={display_num}")
            return display_num
        except Exception as e:
            logger.warning(f"Не удалось запустить xvfb: {e}. Используем headless режим.")
            return None
    
    def _get_browser(self) -> BaseBrowserAutomation:
        """Создает и возвращает экземпляр браузера."""
        # Проверяем флаг обновления сессии
        update_session = os.getenv('UPDATE_INSTAGRAM_SESSION', 'false').lower() == 'true'

        # Проверяем наличие сохраненной сессии
        session_data = self.session_manager.load_session(self.credentials)
        has_saved_session = bool(session_data and session_data.get('cookies'))

        # Если нужно обновить сессию - игнорируем сохраненную
        if update_session:
            has_saved_session = False
            logger.info("🔄 Режим обновления сессии Instagram - игнорируем сохраненную сессию")
        
        # Проверяем флаг обновления сессии - ВЫСШИЙ ПРИОРИТЕТ
        if update_session:
            # Режим обновления сессии - всегда видимый браузер
            headless = False
            logger.info("🔄 Режим обновления сессии: Браузер запускается в видимом режиме")
            logger.info("👁️ Авторизуйтесь в Instagram вручную и закройте браузер")
            logger.info("📝 Сессия будет сохранена автоматически")
        else:
            # Проверяем переменную окружения для отладки (видимый режим) - ВЫСШИЙ ПРИОРИТЕТ
            browser_debug = os.getenv('BROWSER_DEBUG', 'false').lower() == 'true'

            if browser_debug:
                # Режим отладки - всегда видимый браузер, независимо от других настроек
                headless = False
                logger.info("🐛 DEBUG MODE: Браузер запускается в видимом режиме для отладки (BROWSER_DEBUG=true)")
                logger.info("👁️ Браузер будет видимым - вы сможете наблюдать все действия в реальном времени")
            else:
                # Используем headless_mode из credentials, если установлен
                headless_from_creds = getattr(self.credentials, 'headless_mode', None)
                headless_from_settings = getattr(settings, 'BROWSER_HEADLESS', True)

                # Если сохраненной сессии нет - проверяем окружение
                if not has_saved_session:
                    is_docker = os.path.exists('/.dockerenv') or os.environ.get('DOCKER_CONTAINER') == 'true'

                    if is_docker:
                        # В Docker нельзя авторизоваться без сохраненной сессии
                        logger.error("❌ Нет сохраненной сессии Instagram для использования в Docker")
                        logger.error("📋 Для первой авторизации запустите локально (не в Docker):")
                        logger.error("   python manage.py shell")
                        logger.error("   >>> from tasks.services.browser_automation.setup_instagram_session import setup_session")
                        logger.error("   >>> from webhooks.models import SocialMediaCredentials")
                        logger.error("   >>> creds = SocialMediaCredentials.objects.get(platform='instagram')")
                        logger.error("   >>> setup_session(creds.id)")
                        # Все равно возвращаем браузер, но он не сможет авторизоваться
                        headless = True
                    else:
                        # Локально - можно использовать видимый браузер
                        headless = False
                        logger.info("⚠️ Сохраненной сессии нет - используем видимый режим для первой авторизации")
                elif headless_from_creds is not None:
                    # Если сессия есть и в credentials явно установлено - используем его
                    headless = headless_from_creds
                    logger.info(f"headless_mode из credentials: {headless}")
                else:
                    # Если сессия есть, но в credentials не установлено - используем settings
                    headless = headless_from_settings
                    logger.info(f"headless_mode из settings: {headless} (credentials не установлено, есть сохраненная сессия)")
        
        # Проверяем, нужно ли использовать undetected-chromedriver для обхода детекции
        use_undetected = os.getenv('USE_UNDETECTED_CHROMEDRIVER', 'false').lower() == 'true'

        if use_undetected:
            logger.info("🛡️ Используем undetected-chromedriver для обхода детекции Instagram")
            browser = SeleniumAutomation(headless=headless)
            return browser

        logger.info(f"Запуск браузера {self.browser_type} в режиме {'headless' if headless else 'видимом'}")

        if self.browser_type == 'playwright':
            browser = PlaywrightAutomation(headless=headless)
            # Для Instagram Reels используем десктопный режим (в десктопной версии можно создать Reels через "Публикация")
            browser.mobile_mode = False
            return browser
        else:
            return SeleniumAutomation(headless=headless)
    
    def _publish_via_graph_api(self, video_path: str, caption: str, share_to_facebook: bool) -> Dict[str, Any]:
        """
        Публикует Reels через Instagram Graph API.
        Требует Business аккаунт и App Review.

        Args:
            video_path: Путь к видео файлу
            caption: Подпись к публикации
            share_to_facebook: Флаг публикации в Facebook

        Returns:
            Dict с результатом публикации
        """
        result = {
            'success': False,
            'instagram_post_id': None,
            'facebook_post_id': None,
            'error': None
        }

        try:
            # Проверяем наличие access_token
            access_token = getattr(self.credentials, 'instagram_access_token', None)
            if not access_token:
                result['error'] = "Instagram Graph API access_token не настроен"
                logger.warning("⚠️ Instagram Graph API недоступен - нет access_token")
                return result

            # Проверяем наличие instagram_business_account_id
            ig_business_id = getattr(self.credentials, 'instagram_business_account_id', None)
            if not ig_business_id:
                result['error'] = "Instagram business_account_id не настроен"
                logger.warning("⚠️ Instagram Graph API недоступен - нет business_account_id")
                return result

            import requests

            # Шаг 1: Загружаем видео на серверы Instagram
            logger.info("📤 Шаг 1: Загрузка видео на Instagram...")

            # Получаем URL для загрузки
            upload_url = f"https://graph.facebook.com/v18.0/{ig_business_id}/media"
            upload_params = {
                'access_token': access_token,
                'media_type': 'REELS',
                'video_url': video_path,  # В реальности нужно загрузить видео на хостинг и передать URL
            }

            # ВНИМАНИЕ: Это упрощенная версия. В реальности нужно:
            # 1. Загрузить видео на сервер (например, через multipart/form-data)
            # 2. Получить media_id
            # 3. Создать публикацию

            logger.warning("⚠️ Instagram Graph API требует:")
            logger.warning("   - Business аккаунт Instagram")
            logger.warning("   - Facebook App с Instagram Basic Display API")
            logger.warning("   - App Review от Facebook")
            logger.warning("   - Правильную загрузку видео через multipart/form-data")

            result['error'] = "Instagram Graph API требует дополнительной настройки"
            return result

        except Exception as e:
            logger.error(f"Ошибка публикации через Graph API: {e}")
            result['error'] = str(e)
            return result

    def _publish_with_manual_upload(self, video_path: str, caption: str, share_to_facebook: bool) -> Dict[str, Any]:
        """
        Публикует Reels с ручной загрузкой файла пользователем.
        Браузер открывается, пользователь загружает файл вручную,
        затем автоматизация продолжает процесс.

        Args:
            video_path: Путь к видео файлу (для информации пользователю)
            caption: Подпись к публикации
            share_to_facebook: Флаг публикации в Facebook

        Returns:
            Dict с результатом публикации
        """
        result = {
            'success': False,
            'instagram_post_id': None,
            'facebook_post_id': None,
            'error': None
        }

        try:
            logger.info("🎯 РЕЖИМ РУЧНОЙ ЗАГРУЗКИ")
            logger.info("📋 Инструкции для пользователя:")
            logger.info(f"   1. Видео находится по пути: {video_path}")
            logger.info("   2. В браузере нажмите 'Выбрать на компьютере'")
            logger.info("   3. Выберите указанный файл")
            logger.info("   4. Дождитесь обработки видео Instagram")
            logger.info("   5. Автоматизация продолжит процесс")
            logger.info("")
            logger.info("⏳ Ожидание загрузки файла пользователем (максимум 5 минут)...")

            # Ждем появления превью видео (максимум 5 минут)
            max_wait = 300  # 5 минут
            preview_found = False

            for attempt in range(max_wait):
                try:
                    # Проверяем, появилось ли превью
                    dialog = self.browser.page.query_selector('div[role="dialog"]')
                    if dialog:
                        video_elem = dialog.query_selector('video, canvas, img[src*="blob"]')
                        if video_elem:
                            logger.info("✅ Превью видео обнаружено!")
                            preview_found = True
                            break

                        # Также проверяем, перешли ли на экран редактирования
                        crop_text = dialog.query_selector('text=/Обрезать|Crop/i')
                        if crop_text:
                            logger.info("✅ Переход на экран редактирования обнаружен!")
                            preview_found = True
                            break

                except Exception as e:
                    logger.debug(f"Ошибка проверки превью: {e}")

                # Каждые 10 секунд показываем статус
                if attempt % 10 == 0:
                    remaining = max_wait - attempt
                    logger.info(f"⏳ Ожидание загрузки файла... Осталось {remaining} сек")

                self.browser.random_delay(1, 1)

            if not preview_found:
                result['error'] = "Пользователь не загрузил файл в течение 5 минут"
                logger.error("❌ Таймаут ожидания загрузки файла пользователем")
                return result

            # Продолжаем обычный процесс публикации
            logger.info("🚀 Продолжаем автоматизацию после ручной загрузки...")

            # Переходим через экраны "Далее"
            self.browser.random_delay(2, 3)

            # Находим и кликаем "Далее" до экрана подписи
            max_next_clicks = 3
            for step in range(max_next_clicks):
                logger.info(f"📍 Шаг {step + 1}: Ищем кнопку 'Далее'...")

                # Проверяем текущий экран
                dialog = self.browser.page.query_selector('div[role="dialog"]')
                if dialog:
                    dialog_text = dialog.inner_text()
                    logger.info(f"📋 Текущий экран содержит: {dialog_text[:100]}...")

                    # Если уже на экране подписи - выходим из цикла
                    if 'Поделиться' in dialog_text or 'Share' in dialog_text:
                        logger.info("✅ Достигнут экран публикации!")
                        break

                # Ищем и кликаем "Далее"
                next_found = False
                next_selectors = [
                    'text=/^Далее$/i',
                    'text=/^Next$/i',
                    'button:has-text("Далее")',
                    'button:has-text("Next")',
                    '[aria-label*="Далее"]',
                    '[aria-label*="Next"]',
                ]

                for selector in next_selectors:
                    try:
                        next_button = self.browser.page.query_selector(selector)
                        if next_button and next_button.is_visible():
                            next_button.click()
                            logger.info(f"✅ Клик на 'Далее' через селектор: {selector}")
                            next_found = True
                            self.browser.random_delay(3, 5)
                            break
                    except:
                        pass

                if not next_found:
                    logger.warning(f"⚠️ Кнопка 'Далее' не найдена на шаге {step + 1}")
                    break

            # Добавляем подпись
            logger.info("📝 Добавляем подпись к публикации...")
            try:
                caption_field = self._find_caption_field()
                if caption_field:
                    caption_field.fill(caption)
                    logger.info(f"✅ Подпись добавлена: {caption[:50]}...")
                else:
                    logger.warning("⚠️ Не удалось найти поле для подписи")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка при добавлении подписи: {e}")

            # Публикуем
            logger.info("📤 Публикуем видео...")
            success = self._click_publish_button()
            if success:
                result['success'] = True
                result['instagram_post_id'] = "manual_upload_success"
                logger.info("✅ Публикация завершена успешно!")
            else:
                result['error'] = "Не удалось нажать кнопку публикации"
                logger.error("❌ Не удалось завершить публикацию")

        except Exception as e:
            logger.error(f"Ошибка в режиме ручной загрузки: {e}")
            result['error'] = str(e)

        return result

    def _check_account_linking(self) -> bool:
        """
        Проверяет, связаны ли аккаунты Instagram и Facebook.
        
        Returns:
            bool: True если аккаунты связаны
        """
        try:
            # Проверяем наличие чекбокса "Также делиться в Facebook"
            # Это делается при загрузке страницы публикации
            facebook_checkbox_selectors = [
                'input[type="checkbox"][aria-label*="Facebook"]',
                'input[type="checkbox"][aria-label*="facebook"]',
                '[aria-label*="Also share to Facebook"]',
                '[aria-label*="Также делиться в Facebook"]',
            ]
            
            for selector in facebook_checkbox_selectors:
                element = self.browser.wait_for_element(selector, timeout=5, visible=False)
                if element:
                    logger.info("Аккаунты Instagram-Facebook связаны")
                    return True
            
            logger.warning("Аккаунты Instagram-Facebook не связаны или чекбокс не найден")
            return False
        except Exception as e:
            logger.warning(f"Ошибка проверки связи аккаунтов: {e}")
            return False
    
    def _login(self) -> bool:
        """
        Выполняет авторизацию в Instagram.
        Использует сохраненную сессию если доступна.
        
        Returns:
            bool: True если авторизация успешна
        """
        try:
            # Пытаемся загрузить сохраненную сессию
            session_data = self.session_manager.load_session(self.credentials)
            if session_data:
                cookies = session_data.get('cookies', [])
                if cookies:
                    logger.info("Используется сохраненная сессия Instagram")
                    self.browser.navigate(self.INSTAGRAM_URL)
                    self.browser.set_cookies(cookies)
                    self.browser.navigate(self.INSTAGRAM_URL)
                    self.browser.random_delay(2, 4)
                    
                    # Проверяем, что авторизация прошла успешно
                    if self._is_logged_in():
                        logger.info("Авторизация через сохраненную сессию успешна")
                        return True
            
            # Если сессия не найдена или невалидна, нужна ручная авторизация
            logger.warning("Сохраненная сессия не найдена. Требуется ручная авторизация.")
            
            # Проверяем, запущены ли мы в Docker
            is_docker = os.path.exists('/.dockerenv') or os.environ.get('DOCKER_CONTAINER') == 'true'
            
            if is_docker:
                logger.error("❌ ОШИБКА: Нет сохраненной сессии, а браузер запущен в Docker (не видимый)")
                logger.error("📋 РЕШЕНИЕ: Выполните первоначальную авторизацию локально:")
                logger.error("   1. Остановите Docker контейнер")
                logger.error("   2. Запустите локально: python manage.py shell")
                logger.error("   3. Выполните:")
                logger.error("      >>> from tasks.services.browser_automation.setup_instagram_session import setup_session")
                logger.error("      >>> from webhooks.models import SocialMediaCredentials")
                logger.error("      >>> creds = SocialMediaCredentials.objects.get(platform='instagram')")
                logger.error("      >>> setup_session(creds.id)")
                logger.error("   4. Авторизуйтесь в открывшемся браузере")
                logger.error("   5. После сохранения сессии можно использовать Docker в headless режиме")
                return False
            
            logger.info(f"Открываем Instagram: {self.INSTAGRAM_URL}")
            logger.info("⚠️ ВАЖНО: Авторизуйтесь вручную в открывшемся браузере")
            
            navigate_success = self.browser.navigate(self.INSTAGRAM_URL)
            if not navigate_success:
                logger.error("❌ Не удалось открыть страницу Instagram")
                return False
            
            # Получаем текущий URL после перехода
            try:
                if hasattr(self.browser, 'page') and self.browser.page:
                    current_url = self.browser.page.url
                    logger.info(f"✅ Страница открыта: {current_url}")
            except Exception as e:
                logger.warning(f"Не удалось получить URL страницы: {e}")
            
            # Ждем авторизации (проверяем каждые 5 секунд, максимум 5 минут)
            max_wait_time = 300
            wait_interval = 5
            elapsed = 0
            
            logger.info(f"⏳ Ожидание авторизации (максимум {max_wait_time} секунд)...")
            
            while elapsed < max_wait_time:
                self.browser.random_delay(wait_interval, wait_interval + 2)
                logger.debug(f"Проверка авторизации... ({elapsed}/{max_wait_time} сек)")
                if self._is_logged_in():
                    # Сохраняем сессию после успешной авторизации
                    cookies = self.browser.get_cookies()
                    self.session_manager.save_session(
                        self.credentials,
                        cookies,
                        self.browser_type
                    )
                    logger.info("✅ Авторизация успешна, сессия сохранена")
                    return True
                elapsed += wait_interval
            
            logger.error("Таймаут ожидания авторизации")
            return False
            
        except Exception as e:
            logger.error(f"Ошибка авторизации: {e}", exc_info=True)
            return False
    
    def _is_logged_in(self) -> bool:
        """Проверяет, авторизован ли пользователь."""
        try:
            # Даем время на загрузку страницы
            self.browser.random_delay(2, 3)
            
            # Получаем текущий URL для отладки
            try:
                if hasattr(self.browser, 'page') and self.browser.page:
                    current_url = self.browser.page.url
                elif hasattr(self.browser, 'get_current_url'):
                    current_url = self.browser.get_current_url()
                else:
                    current_url = 'unknown'
            except:
                current_url = 'unknown'
            logger.info(f"Проверка авторизации. Текущий URL: {current_url}")
            
            # Проверяем наличие элементов, которые появляются только после авторизации
            logged_in_selectors = [
                'a[href*="/direct/inbox/"]',  # Иконка сообщений
                'a[href*="/accounts/activity/"]',  # Иконка активности
                'svg[aria-label="Home"]',  # Иконка дома
                'svg[aria-label*="Home"]',  # Вариант с другим регистром
                'a[href="/"]',  # Ссылка на главную
            ]
            
            for selector in logged_in_selectors:
                try:
                    element = self.browser.wait_for_element(selector, timeout=5, visible=False)
                    if element:
                        logger.info(f"✅ Найден элемент авторизации: {selector}")
                        return True
                except Exception as e:
                    logger.debug(f"Элемент {selector} не найден: {e}")
            
            # Дополнительная проверка: ищем элементы страницы входа
            login_selectors = [
                'input[name="username"]',
                'input[type="text"][aria-label*="username"]',
                'button[type="submit"]',
            ]
            
            login_page_detected = False
            for selector in login_selectors:
                try:
                    element = self.browser.wait_for_element(selector, timeout=2, visible=False)
                    if element:
                        logger.info(f"⚠️ Найдена страница входа (элемент: {selector})")
                        login_page_detected = True
                        break
                except:
                    pass
            
            if login_page_detected:
                logger.warning("Обнаружена страница входа - авторизация не выполнена")
                return False
            
            logger.warning("Не удалось определить статус авторизации")
            return False
        except Exception as e:
            logger.error(f"Ошибка проверки авторизации: {e}", exc_info=True)
            return False
    
    def _download_video(self, video_url: str) -> Optional[str]:
        """
        Скачивает видео по URL во временный файл.
        Проверяет что это действительно видео, а не картинка.
        
        Args:
            video_url: URL видео
            
        Returns:
            str: Путь к временному файлу или None при ошибке
        """
        try:
            # Получаем заголовки для проверки типа контента
            head_response = requests.head(video_url, timeout=30, allow_redirects=True)
            content_type = head_response.headers.get('Content-Type', '').lower()
            
            # Проверяем что это видео, а не изображение
            if content_type.startswith('image/'):
                error_msg = f"URL указывает на изображение ({content_type}), а не на видео. Instagram Reels требует видео."
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            if not content_type.startswith('video/') and not any(ext in video_url.lower() for ext in ['.mp4', '.mov', '.avi', '.webm']):
                logger.warning(f"⚠️ Content-Type: {content_type}. Возможно это не видео. Продолжаем загрузку...")
            
            # Скачиваем файл
            response = requests.get(video_url, stream=True, timeout=60)
            response.raise_for_status()
            
            # Определяем расширение из URL или Content-Type
            file_extension = '.mp4'  # По умолчанию
            if content_type.startswith('video/'):
                # Извлекаем расширение из MIME типа (video/mp4 -> .mp4)
                mime_to_ext = {
                    'video/mp4': '.mp4',
                    'video/quicktime': '.mov',
                    'video/x-msvideo': '.avi',
                    'video/webm': '.webm',
                    'video/mpeg': '.mpeg',
                }
                file_extension = mime_to_ext.get(content_type.split(';')[0], '.mp4')
            else:
                # Пытаемся определить из URL
                url_lower = video_url.lower()
                for ext in ['.mp4', '.mov', '.avi', '.webm', '.mpeg']:
                    if ext in url_lower:
                        file_extension = ext
                        break
            
            # Создаем временный файл с правильным расширением
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_extension)
            file_size = 0
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    temp_file.write(chunk)
                    file_size += len(chunk)
            temp_file.close()
            
            # Проверяем размер файла (минимум 1KB)
            if file_size < 1024:
                error_msg = f"Файл слишком маленький ({file_size} байт). Возможно это не видео."
                logger.error(error_msg)
                os.unlink(temp_file.name)  # Удаляем файл
                raise ValueError(error_msg)
            
            logger.info(f"✅ Видео скачано: {temp_file.name} ({file_size / 1024 / 1024:.2f} MB, тип: {content_type})")
            return temp_file.name
        except ValueError:
            # Пробрасываем ошибки валидации
            raise
        except Exception as e:
            logger.error(f"Ошибка скачивания видео: {e}", exc_info=True)
            return None
    
    def publish_reels(
        self,
        video_url: str,
        caption: str = "",
        share_to_facebook: bool = True,
        add_to_story: bool = True,
        hashtags: list = None
    ) -> Dict[str, Any]:
        """
        Публикует Reels в Instagram с опциональным кросспостингом.
        
        Args:
            video_url: URL видео для публикации
            caption: Подпись к Reels
            share_to_facebook: Публиковать ли в Facebook (если аккаунты связаны)
            add_to_story: Добавлять ли в Instagram Stories
            hashtags: Список хештегов
            
        Returns:
            Dict с результатами публикации:
            {
                'success': bool,
                'instagram_post_id': str,
                'facebook_post_id': str (если share_to_facebook=True),
                'instagram_story_id': str (если add_to_story=True),
                'error': str (если success=False)
            }
        """
        result = {
            'success': False,
            'instagram_post_id': None,
            'facebook_post_id': None,
            'instagram_story_id': None,
            'error': None
        }

        # Проверяем флаг обновления сессии
        update_session = os.getenv('UPDATE_INSTAGRAM_SESSION', 'false').lower() == 'true'

        video_path = None
        
        try:
            # Инициализируем браузер
            self.browser = self._get_browser()
            if not self.browser.start_browser():
                result['error'] = "Не удалось запустить браузер"
                return result
            
            # Авторизация
            if not self._login():
                result['error'] = "Ошибка авторизации в Instagram"
                return result
            
            # Режим обновления сессии - просто сохраняем и выходим
            if update_session:
                logger.info("🔄 Режим обновления сессии Instagram")
                logger.info("📋 Инструкции:")
                logger.info("   1. Авторизуйтесь в Instagram в открывшемся браузере")
                logger.info("   2. После авторизации закройте браузер")
                logger.info("   3. Сессия будет сохранена автоматически")
                logger.info("")
                logger.info("⏳ Ожидание авторизации пользователя...")
                logger.info("📋 Важно: После авторизации ЗАКРОЙТЕ браузер вручную!")

                # Ждем пока пользователь авторизуется и закроет браузер
                try:
                    import time
                    logger.info("💡 Выполните авторизацию в открывшемся браузере")
                    logger.info("💡 После успешной авторизации закройте окно браузера")
                    logger.info("⏳ Максимальное время ожидания: 10 минут")

                    # Ждем максимум 10 минут (600 секунд)
                    max_wait = 600
                    for i in range(max_wait):
                        time.sleep(1)

                        # Каждые 10 секунд показываем статус
                        if i % 10 == 0:
                            remaining = max_wait - i
                            logger.info(f"⏳ Ожидание закрытия браузера... Осталось {remaining} сек")
                            logger.info("💡 Закройте браузер после авторизации!")

                        # Проверяем, не закрыт ли браузер
                        try:
                            self.browser.page.url  # Простая проверка
                        except:
                            logger.info("✅ Браузер закрыт пользователем - сохраняем сессию")
                            break
                    else:
                        # Если цикл завершился без break - таймаут
                        logger.warning("⚠️ Таймаут ожидания! Браузер все еще открыт")
                        logger.warning("💡 Закройте браузер вручную для сохранения сессии")

                    # Сохраняем сессию
                    logger.info("💾 Сохранение сессии Instagram...")
                    self.session_manager.save_session(self.credentials, self.browser.page.context)
                    logger.info("✅ Сессия Instagram сохранена!")

                    result['success'] = True
                    result['message'] = "Сессия Instagram обновлена успешно"
                    return result

                except Exception as e:
                    logger.error(f"Ошибка при обновлении сессии: {e}")
                    result['error'] = f"Ошибка при обновлении сессии: {str(e)}"
                    return result

            # Скачиваем видео с проверкой типа файла
            try:
                video_path = self._download_video(video_url)
                if not video_path:
                    result['error'] = "Не удалось скачать видео"
                    return result
            except ValueError as e:
                # Ошибка валидации (не видео, слишком маленький файл и т.д.)
                result['error'] = str(e)
                logger.error(f"❌ Ошибка валидации видео: {e}")
                return result
            
            # Шаг 1: Переходим на главную страницу Instagram
            logger.info(f"Переход на главную страницу Instagram: {self.INSTAGRAM_URL}")
            if not self.browser.navigate(self.INSTAGRAM_URL):
                result['error'] = "Не удалось открыть главную страницу Instagram"
                return result
            
            self.browser.random_delay(2, 3)
            
            # Шаг 2: Кликаем "Создать" -> "Публикация"
            logger.info("🔍 Ищем кнопку 'Создать'...")
            
            # Логируем текущий URL
            try:
                if hasattr(self.browser, 'page') and self.browser.page:
                    current_url = self.browser.page.url
                    logger.info(f"📍 Текущий URL: {current_url}")
            except:
                pass
            
            create_clicked = False
            try:
                if hasattr(self.browser, 'page') and self.browser.page:
                    from playwright.sync_api import Page
                    if isinstance(self.browser.page, Page):
                        # ПРИОРИТЕТ: Ищем через data-cursor-element-id (как показал пользователь в DOM)
                        try:
                            create_elements = self.browser.page.query_selector_all('[data-cursor-element-id]')
                            logger.info(f"🔍 Найдено {len(create_elements)} элементов с data-cursor-element-id, ищем 'Создать'...")
                            for elem in create_elements:
                                try:
                                    text = (elem.inner_text() or elem.text_content() or '').strip()
                                    # Проверяем точное совпадение (только текст "Создать" или "Create", без лишнего)
                                    if text in ['Создать', 'Create']:
                                        # Дополнительная проверка - элемент должен быть небольшим (не весь контент страницы)
                                        bounding_box = elem.bounding_box()
                                        if bounding_box:
                                            # Если элемент слишком большой (больше 200px по высоте) - это не кнопка, а контейнер
                                            if bounding_box['height'] > 200:
                                                logger.debug(f"Пропускаем элемент '{text}' - слишком большой ({bounding_box['height']}px)")
                                                continue
                                        
                                        logger.info(f"✅ Найдена кнопка 'Создать' через data-cursor-element-id, текст: '{text}', кликаем...")
                                        elem.click(timeout=5000)
                                        create_clicked = True
                                        logger.info("⏳ Ждем появления меню (3-5 секунд)...")
                                        self.browser.random_delay(3, 5)
                                        break
                                except Exception as e:
                                    logger.debug(f"Ошибка при проверке элемента: {e}")
                                    continue
                        except Exception as e:
                            logger.debug(f"Ошибка поиска через data-cursor-element-id: {e}")
                        
                        # Если не нашли через data-cursor-element-id, пробуем другие селекторы
                        # ВАЖНО: Исключаем профили пользователей (они тоже могут содержать "Create")
                        if not create_clicked:
                            create_selectors = [
                                # Ищем только в навигации, не в профилях
                                'a:has-text("Создать"):not([href*="/"])',  # Создать без ссылки на профиль
                                'a[href="#"]:has-text("Создать")',  # Создать с href="#"
                                'div:has-text("Создать"):not(:has-text("Подписки")):not([href])',  # Создать в меню, не профиль
                                '[aria-label*="Создать"]:not([href*="/"])',  # aria-label без ссылки на профиль
                            ]
                            
                            for selector in create_selectors:
                                try:
                                    create_locator = self.browser.page.locator(selector).first
                                    if create_locator.is_visible(timeout=5000):
                                        text = create_locator.inner_text() or create_locator.text_content() or ''
                                        # Проверяем, что текст короткий (только "Создать" или "Create")
                                        if len(text.strip()) > 50:  # Если текст длинный - это не кнопка
                                            logger.debug(f"Пропускаем '{selector}' - слишком длинный текст ({len(text)} символов)")
                                            continue
                                        
                                        tag_name = ''
                                        try:
                                            tag_name = create_locator.evaluate('el => el.tagName').lower()
                                        except:
                                            pass
                                        
                                        logger.info(f"✅ Найдена кнопка 'Создать' через селектор: {selector}, текст: '{text[:50]}', тег: {tag_name}, кликаем...")
                                        
                                        # Пробуем JavaScript клик для большей надежности
                                        try:
                                            create_locator.evaluate('element => element.click()')
                                            logger.info("✅ JavaScript клик выполнен")
                                        except Exception as js_e:
                                            logger.warning(f"JavaScript клик не сработал: {js_e}, пробуем обычный клик")
                                            create_locator.click(timeout=5000)
                                            logger.info("✅ Обычный клик выполнен")
                                        
                                        create_clicked = True
                                        logger.info("⏳ Ждем появления меню (3-5 секунд)...")
                                        self.browser.random_delay(3, 5)
                                        break
                                except Exception as e:
                                    logger.debug(f"Ошибка поиска через {selector}: {e}")
                                    continue
            except Exception as e:
                logger.error(f"Ошибка при поиске кнопки 'Создать': {e}")
            
            if not create_clicked:
                result['error'] = "Не удалось найти кнопку 'Создать' на странице"
                return result
            
            # Шаг 3: Кликаем "Публикация" в меню
            logger.info("🔍 Ищем 'Публикация' в меню...")
            pub_clicked = False
            
            # Сначала логируем все элементы меню для диагностики
            try:
                if hasattr(self.browser, 'page') and self.browser.page:
                    from playwright.sync_api import Page
                    if isinstance(self.browser.page, Page):
                        # Логируем все видимые элементы в меню
                        menu_items = self.browser.page.query_selector_all('a[href*="/create"], div[role="button"], a, div')
                        logger.info(f"📊 Найдено {len(menu_items)} потенциальных элементов меню")
                        
                        visible_texts = []
                        for elem in menu_items[:20]:  # Первые 20 элементов
                            try:
                                text = (elem.inner_text() or elem.text_content() or '').strip()
                                if text and len(text) < 50:  # Короткие тексты (названия пунктов меню)
                                    visible_texts.append(text)
                            except:
                                pass
                        
                        if visible_texts:
                            logger.info(f"📋 Найденные тексты в меню: {visible_texts[:10]}")
            except Exception as e:
                logger.debug(f"Ошибка при логировании элементов меню: {e}")
            
            try:
                if hasattr(self.browser, 'page') and self.browser.page:
                    from playwright.sync_api import Page
                    if isinstance(self.browser.page, Page):
                        # Приоритетные селекторы для "Публикация" в выпадающем меню
                        pub_selectors = [
                            'a[href="/create/select/"]',  # Прямая ссылка на создание публикации (приоритет)
                            'a[href*="/create/select"]',  # Альтернативная ссылка
                            'text=/^Публикация$|^Publication$/i',  # Точное совпадение текста
                            'a:has-text("Публикация")',
                            'a:has-text("Publication")',
                            'div:has-text("Публикация"):visible',  # Только видимые элементы
                            'div:has-text("Publication"):visible',
                        ]
                        
                        for selector in pub_selectors:
                            try:
                                pub_locator = self.browser.page.locator(selector).first
                                # Проверяем видимость с большим таймаутом
                                if pub_locator.is_visible(timeout=8000):
                                    text = pub_locator.inner_text() or pub_locator.text_content() or ''
                                    href = pub_locator.get_attribute('href') or ''
                                    logger.info(f"✅ Найден элемент через селектор: {selector}, текст: '{text}', href: '{href}', кликаем...")
                                    
                                    # Пробуем JavaScript клик для большей надежности
                                    try:
                                        pub_locator.evaluate('element => element.click()')
                                        logger.info("✅ JavaScript клик на 'Публикация' выполнен")
                                    except:
                                        pub_locator.click(timeout=5000)
                                        logger.info("✅ Обычный клик на 'Публикация' выполнен")
                                    
                                    pub_clicked = True
                                    self.browser.random_delay(2, 3)
                                    break
                            except Exception as e:
                                logger.debug(f"Ошибка поиска 'Публикация' через {selector}: {e}")
                                continue
                    
                    # Если не нашли через селекторы, пробуем через поиск по всем ссылкам с текстом "Публикация"
                    if not pub_clicked:
                        try:
                            logger.info("🔍 Поиск 'Публикация' через все ссылки...")
                            # Ищем все ссылки, которые содержат текст "Публикация" или "Publication"
                            all_links = self.browser.page.query_selector_all('a[href*="/create"], a')
                            logger.info(f"📊 Проверяем {len(all_links)} ссылок...")
                            
                            for link in all_links:
                                try:
                                    text = (link.inner_text() or link.text_content() or '').strip()
                                    href = link.get_attribute('href') or ''
                                    
                                    # Проверяем точное совпадение текста
                                    if text in ['Публикация', 'Publication']:
                                        logger.info(f"✅ Найдена 'Публикация' (текст: '{text}', href: '{href}'), кликаем...")
                                        link.click(timeout=5000)
                                        pub_clicked = True
                                        self.browser.random_delay(2, 3)
                                        break
                                except Exception as e:
                                    logger.debug(f"Ошибка при проверке ссылки: {e}")
                                    continue
                        except Exception as e:
                            logger.debug(f"Ошибка поиска 'Публикация' через ссылки: {e}")
                    
                    # Если все еще не нашли, пробуем кликнуть на первую ссылку с /create/
                    if not pub_clicked:
                        try:
                            logger.info("🔍 Пробуем кликнуть на первую ссылку с /create/...")
                            create_link = self.browser.page.locator('a[href*="/create/"]').first
                            if create_link.is_visible(timeout=3000):
                                href = create_link.get_attribute('href') or ''
                                text = create_link.inner_text() or create_link.text_content() or ''
                                logger.info(f"✅ Найдена ссылка на создание: href='{href}', текст='{text}', кликаем...")
                                create_link.click(timeout=5000)
                                pub_clicked = True
                                self.browser.random_delay(2, 3)
                        except Exception as e:
                            logger.warning(f"Не удалось кликнуть на ссылку /create/: {e}")
            except Exception as e:
                logger.error(f"Ошибка при поиске 'Публикация': {e}")
            
            if not pub_clicked:
                result['error'] = "Не удалось найти 'Публикация' в меню после клика на 'Создать'. Возможно, Instagram изменил интерфейс."
                return result
            
            # Шаг 4: Ждем открытия диалога создания публикации
            logger.info("⏳ Ожидание открытия диалога создания публикации...")
            try:
                if hasattr(self.browser, 'page') and self.browser.page:
                    # Ждем появления диалога
                    self.browser.page.wait_for_selector('div[role="dialog"][aria-label*="Создание"], div[role="dialog"][aria-label*="Create"], input[type="file"]', timeout=15000)
                    logger.info("✅ Диалог создания публикации открыт")
            except Exception as e:
                logger.warning(f"Диалог не найден или input не появился, продолжаем... {e}")
            
            self.browser.random_delay(2, 3)
            
            # Ждем полной загрузки страницы (networkidle)
            try:
                if hasattr(self.browser, 'page') and self.browser.page:
                    logger.info("⏳ Ожидание полной загрузки страницы (networkidle)...")
                    self.browser.page.wait_for_load_state("networkidle", timeout=30000)
                    logger.info("✅ Страница загружена (networkidle)")
            except Exception as e:
                logger.warning(f"⚠️ Не удалось дождаться networkidle: {e}, продолжаем...")
            
            # Шаг 5: Загружаем видео через input[type="file"] внутри диалога
            # Механизм загрузки:
            # 1. Instagram показывает диалог div[role="dialog"] с текстом "Перетащите сюда фото и видео"
            # 2. Внутри диалога есть скрытый input[type="file"] элемент
            # 3. Мы находим этот input и устанавливаем файл через set_input_files()
            # 4. Instagram автоматически обрабатывает файл и переходит к следующему экрану
            logger.info("📹 Загрузка видео...")
            uploaded = False
            skip_intermediate_steps = False  # Флаг для пропуска промежуточных шагов после успешной загрузки через filechooser
            
            try:
                if hasattr(self.browser, 'page') and self.browser.page:
                    from playwright.sync_api import Page
                    if isinstance(self.browser.page, Page):
                        # Сначала ждем появления диалога создания публикации
                        logger.info("⏳ Ожидание появления диалога создания публикации...")
                        try:
                            dialog = self.browser.page.wait_for_selector(
                                'div[role="dialog"][aria-label*="Создание"], div[role="dialog"][aria-label*="Create"]',
                                timeout=10000,
                                state='visible'
                            )
                            logger.info("✅ Диалог создания публикации найден")
                        except:
                            # Пробуем найти диалог по другому селектору
                            try:
                                dialog = self.browser.page.wait_for_selector('div[role="dialog"]', timeout=10000, state='visible')
                                logger.info("✅ Диалог найден (общий селектор)")
                            except Exception as e:
                                logger.warning(f"⚠️ Диалог не найден: {e}")
                                dialog = None
                        
                        # Ищем input[type="file"] внутри диалога (приоритет) или на всей странице
                        file_inputs = []
                        if dialog:
                            # Ищем input внутри диалога
                            logger.info("🔍 Ищем input[type='file'] внутри диалога...")
                            file_inputs = dialog.query_selector_all('input[type="file"]')
                            logger.info(f"🔍 Найдено {len(file_inputs)} input[type='file'] элементов внутри диалога")
                        
                        # Если не нашли в диалоге, ищем на всей странице
                        if not file_inputs:
                            logger.info("🔍 Ищем input[type='file'] на всей странице...")
                            try:
                                self.browser.page.wait_for_selector('input[type="file"]', timeout=10000, state='attached')
                                file_inputs = self.browser.page.query_selector_all('input[type="file"]')
                                logger.info(f"🔍 Найдено {len(file_inputs)} input[type='file'] элементов на странице")
                            except Exception as e:
                                logger.warning(f"input[type='file'] не найден на странице: {e}")
                        
                        # ========================================
                        # ТАКЖЕ: Проверка формата видео
                        # Возможно Instagram не поддерживает этот формат
                        # ========================================

                        # ========================================
                        # ИСПРАВЛЕНИЕ: Переименована переменная subprocess
                        # ========================================

                        # ДОБАВЬТЕ ПЕРЕД загрузкой файла:
                        logger.info("🔍 Проверяем формат видео перед загрузкой...")
                        try:
                            import subprocess
                            import json

                            # Используем ffprobe для проверки видео
                            ffprobe_result = subprocess.run(  # ← ПЕРЕИМЕНОВАНО! БЫЛО result
                                ['ffprobe', '-v', 'error', '-show_entries',
                                 'format=format_name,duration,size', '-of', 'json', video_path],
                                capture_output=True,
                                text=True,
                                timeout=10
                            )

                            if ffprobe_result.returncode == 0 and ffprobe_result.stdout:  # ← Используем ffprobe_result
                                video_info = json.loads(ffprobe_result.stdout)
                                format_info = video_info.get('format', {})

                                logger.info(f"📹 Формат видео: {format_info.get('format_name')}")
                                logger.info(f"📹 Длительность: {format_info.get('duration')} секунд")
                                logger.info(f"📹 Размер: {int(format_info.get('size', 0)) / 1024 / 1024:.2f} MB")

                                # Проверяем ограничения Instagram Reels
                                try:
                                    duration = float(format_info.get('duration', 0))
                                    size_mb = int(format_info.get('size', 0)) / 1024 / 1024

                                    if duration > 90:
                                        logger.warning(f"⚠️ Видео слишком длинное для Reels: {duration} секунд (максимум 90)")

                                    if size_mb > 650:
                                        logger.warning(f"⚠️ Видео слишком большое: {size_mb:.2f} MB (максимум 650 MB)")
                                except (ValueError, TypeError) as e:
                                    logger.debug(f"Не удалось проверить ограничения: {e}")
                            else:
                                logger.warning("⚠️ ffprobe вернул ошибку или пустой результат")

                        except FileNotFoundError:
                            logger.info("ℹ️ ffprobe не установлен - пропускаем проверку формата видео")
                        except subprocess.TimeoutExpired:
                            logger.warning("⚠️ ffprobe завис - пропускаем проверку формата")
                        except Exception as e:
                            logger.warning(f"⚠️ Ошибка проверки формата видео: {e}")

                        # НОВЫЙ ПОДХОД: Используем реальный клик на кнопку "Выбрать на компьютере" с перехватом filechooser
                        # Это более надежный способ, так как Instagram может блокировать программную установку файла
                        logger.info("📤 Используем клик на кнопку 'Выбрать на компьютере' с перехватом filechooser...")

                        # Инициализируем переменные перед использованием
                        preview_appeared = False

                        try:
                            # Ищем кнопку "Выбрать на компьютере"
                            select_button = None
                            try:
                                select_button = self.browser.page.locator('text=/Выбрать на компьютере|Select from computer/i').first
                                if select_button.count() == 0:
                                    # Пробуем найти через aria-label или другие атрибуты
                                    select_button = self.browser.page.locator('button:has-text("Выбрать"), button:has-text("Select")').first
                            except:
                                pass
                            
                            if select_button and select_button.count() > 0:
                                logger.info("✅ Найдена кнопка 'Выбрать на компьютере'")
                                logger.info("📤 Используем правильный метод filechooser...")

                                try:
                                    # КРИТИЧЕСКИ ВАЖНО: Перехватываем filechooser ПЕРЕД кликом
                                    # и устанавливаем файл ВНУТРИ контекстного менеджера

                                    # Способ 1: С контекстным менеджером (правильный)
                                    with self.browser.page.expect_file_chooser() as fc_info:
                                        # Кликаем ВНУТРИ контекста
                                        select_button.click()
                                        logger.info("✅ Клик на кнопку выполнен, ждем filechooser...")

                                    # Получаем filechooser
                                    file_chooser = fc_info.value

                                    # Устанавливаем файл
                                    file_chooser.set_files(video_path)
                                    logger.info("✅ Файл установлен через filechooser")

                                    uploaded = True

                                    # Ждем обработки Instagram
                                    logger.info("⏳ Ждем обработки файла Instagram (10-12 секунд)...")
                                    self.browser.random_delay(10, 12)

                                except Exception as fc_error:
                                    logger.error(f"❌ Ошибка filechooser: {fc_error}")
                                    uploaded = False

                                    # Fallback: Пробуем установить файл напрямую в input
                                    logger.info("🔄 Fallback: Устанавливаем файл напрямую в input...")
                                    try:
                                        file_input = self.browser.page.query_selector('div[role="dialog"] input[type="file"]')

                                        if file_input:
                                            file_input.set_input_files(video_path)
                                            logger.info("✅ Файл установлен в input (fallback)")

                                            # Триггерим события
                                            self.browser.page.evaluate('''(input) => {
                                                ['input', 'change'].forEach(eventType => {
                                                    const event = new Event(eventType, { bubbles: true });
                                                    input.dispatchEvent(event);
                                                });
                                            }''', file_input)

                                            uploaded = True
                                            self.browser.random_delay(10, 12)
                                        else:
                                            logger.error("❌ input[type='file'] не найден")

                                    except Exception as fallback_error:
                                        logger.error(f"❌ Fallback тоже не сработал: {fallback_error}")
                            else:
                                logger.error("❌ Кнопка 'Выбрать на компьютере' не найдена")
                                uploaded = False

                            # Проверяем результат
                            if uploaded:
                                logger.info("🔍 Проверяем результат загрузки...")
                                try:
                                    dialog = self.browser.page.query_selector('div[role="dialog"]')
                                    if dialog:
                                        dialog_text = dialog.inner_text()

                                        # Проверяем, что экран изменился
                                        if 'Перетащите' in dialog_text or 'Выбрать на компьютере' in dialog_text:
                                            logger.error("❌ Instagram не принял файл - все еще на экране загрузки")
                                            logger.info("  input[type='file'].files.length после загрузки:")

                                            file_inputs = dialog.query_selector_all('input[type="file"]')
                                            for i, inp in enumerate(file_inputs):
                                                try:
                                                    files_count = self.browser.page.evaluate('(input) => input.files ? input.files.length : 0', inp)
                                                    logger.info(f"    input[{i}]: {files_count} файлов")
                                                except:
                                                    pass

                                            uploaded = False
                                        else:
                                            # Проверяем наличие превью
                                            has_preview = dialog.query_selector('video, canvas, img[src*="blob"]')
                                            if has_preview:
                                                logger.info("✅ Файл успешно загружен! Превью найдено")
                                            else:
                                                logger.warning(f"⚠️ Экран изменился, но превью не найдено: {dialog_text[:200]}")
                                except Exception as e:
                                    logger.warning(f"Ошибка проверки: {e}")


                            # ========================================
                            # ПРОВЕРКА: Возможно пользователь хочет ручную загрузку
                            # ========================================

                            manual_upload_enabled = os.getenv('USE_MANUAL_UPLOAD', 'false').lower() == 'true'
                            if not uploaded and manual_upload_enabled:
                                logger.info("🎯 Включен режим ручной загрузки файла...")
                                manual_result = self._publish_with_manual_upload(video_path, caption, share_to_facebook)
                                if manual_result.get('success'):
                                    logger.info("✅ Успешная публикация с ручной загрузкой!")
                                    return manual_result
                                else:
                                    logger.warning(f"⚠️ Ручная загрузка не удалась: {manual_result.get('error')}")

                            # ========================================
                            # АЛЬТЕРНАТИВА: Если filechooser вообще не работает
                            # Используем CDP (Chrome DevTools Protocol)
                            # ========================================

                            if not uploaded:
                                logger.info("🧪 ЭКСПЕРИМЕНТАЛЬНЫЙ МЕТОД: Используем CDP для установки файла...")

                                try:
                                    # Читаем файл как base64
                                    import base64
                                    with open(video_path, 'rb') as f:
                                        file_content = base64.b64encode(f.read()).decode('utf-8')

                                    # Используем CDP для установки файла
                                    cdp_result = self.browser.page.context.new_cdp_session(self.browser.page).send(
                                        'DOM.setFileInputFiles',
                                        {
                                            'files': [video_path],
                                            'nodeId': None,  # Будет найдено автоматически
                                        }
                                    )

                                    logger.info("✅ Файл установлен через CDP")
                                    uploaded = True
                                    self.browser.random_delay(10, 12)

                                except Exception as cdp_error:
                                    logger.error(f"❌ CDP метод не сработал: {cdp_error}")
                                    uploaded = False


                            # ========================================
                            # ФИНАЛЬНАЯ ПРОВЕРКА
                            # ========================================

                            if not uploaded:
                                logger.error("=" * 70)
                                logger.error("❌ ВСЕ МЕТОДЫ ЗАГРУЗКИ НЕ СРАБОТАЛИ")
                                logger.error("=" * 70)
                                logger.error("")
                                logger.error("Instagram блокирует программную загрузку файлов.")
                                logger.error("")
                                logger.error("🔧 Возможные решения:")
                                logger.error("")
                                logger.error("1. Instagram Graph API (официальный способ)")
                                logger.error("   - Требует Business аккаунт")
                                logger.error("   - Требует App Review")
                                logger.error("   - https://developers.facebook.com/docs/instagram-api/")
                                logger.error("")
                                logger.error("2. Undetected ChromeDriver (обход детекции)")
                                logger.error("   - pip install undetected-chromedriver")
                                logger.error("   - Маскируется под обычный Chrome")
                                logger.error("")
                                logger.error("3. Playwright Stealth Plugin")
                                logger.error("   - npm install playwright-extra playwright-extra-plugin-stealth")
                                logger.error("   - Скрывает признаки автоматизации")
                                logger.error("")
                                logger.error("4. Ручная загрузка")
                                logger.error("   - Открыть браузер и попросить пользователя загрузить вручную")
                                logger.error("")
                                logger.error("5. Ручная загрузка с автоматизацией остального")
                                logger.error("   - Браузер откроется, пользователь загрузит файл вручную")
                                logger.error("   - Автоматизация продолжит процесс (подпись, публикация)")
                                logger.error("")
                                logger.error("=" * 70)

                                # Попробуем ручную загрузку как промежуточный вариант
                                logger.info("🔄 Попытка с ручной загрузкой файла...")
                                manual_result = self._publish_with_manual_upload(video_path, caption, share_to_facebook)
                                if manual_result.get('success'):
                                    logger.info("✅ Успешная публикация с ручной загрузкой!")
                                    return manual_result
                                else:
                                    logger.warning(f"⚠️ Ручная загрузка не удалась: {manual_result.get('error')}")

                                # Попробуем Instagram Graph API как последний шанс
                                logger.info("🔄 Попытка публикации через Instagram Graph API...")
                                api_result = self._publish_via_graph_api(video_path, caption, share_to_facebook)
                                if api_result.get('success'):
                                    logger.info("✅ Успешная публикация через Instagram Graph API!")
                                    return api_result
                                else:
                                    logger.warning(f"❌ Graph API тоже не сработал: {api_result.get('error')}")

                                result['error'] = "Instagram блокирует программную загрузку файлов. Попробуйте Instagram Graph API."
                                return result

                                # ДОБАВЬТЕ ЭТО: КРИТИЧЕСКАЯ ДИАГНОСТИКА
                                logger.info("📸 ДИАГНОСТИКА: Делаем скриншот после загрузки файла")
                                try:
                                    import datetime
                                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                                    screenshot_path = f"/tmp/instagram_after_upload_{timestamp}.png"
                                    self.browser.page.screenshot(path=screenshot_path, full_page=True)
                                    logger.info(f"📸 Скриншот сохранен: {screenshot_path}")
                                except Exception as e:
                                    logger.warning(f"Не удалось сделать скриншот: {e}")

                                # КРИТИЧЕСКИ ВАЖНО: Проверяем РЕАЛЬНОЕ содержимое диалога
                                logger.info("🔍 ДИАГНОСТИКА: Проверяем содержимое диалога")
                                try:
                                    # Получаем весь текст диалога
                                    dialog = self.browser.page.query_selector('div[role="dialog"]')
                                    if dialog:
                                        dialog_text = dialog.inner_text()
                                        logger.info("📋 Текст внутри диалога (первые 500 символов):")
                                        logger.info(f"{dialog_text[:500]}")

                                        # Проверяем ключевые слова
                                        keywords = {
                                            'Перетащите': 'На экране загрузки файла',
                                            'Выбрать на компьютере': 'На экране загрузки файла',
                                            'Обрезать': 'На экране обрезки',
                                            'Crop': 'На экране обрезки',
                                            'Далее': 'Есть кнопка Далее',
                                            'Next': 'Есть кнопка Next',
                                            'Редактировать': 'На экране редактирования',
                                            'Edit': 'На экране редактирования',
                                            'Фильтры': 'На экране фильтров',
                                            'Filters': 'На экране фильтров',
                                            'Поделиться': 'На финальном экране',
                                            'Share': 'На финальном экране',
                                            'Добавьте подпись': 'На финальном экране',
                                            'Write a caption': 'На финальном экране',
                                        }

                                        found_keywords = []
                                        for keyword, meaning in keywords.items():
                                            if keyword in dialog_text:
                                                found_keywords.append(f"{keyword} ({meaning})")

                                        if found_keywords:
                                            logger.info(f"🔍 Найденные ключевые слова: {', '.join(found_keywords)}")
                                        else:
                                            logger.warning("⚠️ Не найдено ни одного ключевого слова!")

                                        # Проверяем URL
                                        current_url = self.browser.page.url
                                        logger.info(f"📍 Текущий URL: {current_url}")

                                        # ФИНАЛЬНОЕ РЕШЕНИЕ: Определяем текущий экран
                                        if 'Перетащите' in dialog_text or 'Выбрать на компьютере' in dialog_text:
                                            logger.error("❌ ВСЕ ЕЩЕ НА ЭКРАНЕ ЗАГРУЗКИ ФАЙЛА!")
                                            logger.error("❌ Файл НЕ БЫЛ загружен или Instagram не обработал его!")
                                            logger.info("🔍 Проверяем input[type='file']:")

                                            # Проверяем, установлен ли файл в input
                                            file_inputs = dialog.query_selector_all('input[type="file"]')
                                            for i, file_input in enumerate(file_inputs):
                                                try:
                                                    files_count = self.browser.page.evaluate('''(input) => {
                                                        return input.files ? input.files.length : 0;
                                                    }''', file_input)
                                                    logger.info(f"  input[{i}]: files.length = {files_count}")
                                                except:
                                                    pass

                                            # Пробуем снова установить файл
                                            logger.info("🔄 Пробуем повторно установить файл...")

                                        elif 'Обрезать' in dialog_text or 'Crop' in dialog_text:
                                            logger.info("✅ На экране обрезки - нужно кликнуть 'Далее'")

                                        elif 'Редактировать' in dialog_text or 'Edit' in dialog_text or 'Фильтры' in dialog_text:
                                            logger.info("✅ На экране редактирования - нужно кликнуть 'Далее'")

                                        elif 'Поделиться' in dialog_text or 'Share' in dialog_text:
                                            logger.info("✅ На финальном экране создания публикации!")

                                        else:
                                            logger.warning("⚠️ Неизвестный экран!")

                                    else:
                                        logger.error("❌ Диалог не найден!")

                                except Exception as e:
                                    logger.error(f"Ошибка диагностики: {e}")

                                # Проверка превью видео
                                logger.info("🔍 Проверяем, появилось ли превью видео...")
                                try:
                                    # Ищем video элемент внутри диалога
                                    dialog = self.browser.page.query_selector('div[role="dialog"]')
                                    if dialog:
                                        video_elem = dialog.query_selector('video')
                                        if video_elem:
                                            is_visible = video_elem.is_visible()
                                            rect = video_elem.bounding_box()

                                            if rect:
                                                logger.info(f"✅ video найден: visible={is_visible}, size={rect['width']}x{rect['height']}")

                                                if is_visible and rect['width'] > 0 and rect['height'] > 0:
                                                    logger.info("✅ Превью видео действительно видно")
                                                    preview_appeared = True
                                                else:
                                                    logger.warning("⚠️ video элемент существует, но не виден или имеет нулевой размер")
                                                    preview_appeared = False
                                            else:
                                                logger.warning("⚠️ Не удалось получить размеры video элемента")
                                                preview_appeared = False
                                        else:
                                            logger.warning("⚠️ video элемент не найден внутри диалога")

                                            # Проверяем, может быть canvas или img
                                            canvas = dialog.query_selector('canvas')
                                            img = dialog.query_selector('img[src*="blob"]')

                                            if canvas:
                                                logger.info("ℹ️ Найден canvas элемент (возможно превью)")
                                                preview_appeared = True
                                            elif img:
                                                logger.info("ℹ️ Найден img[src*='blob'] элемент (возможно превью)")
                                                preview_appeared = True
                                            else:
                                                logger.error("❌ Превью не найдено (ни video, ни canvas, ни img)")
                                                preview_appeared = False
                                    else:
                                        logger.error("❌ Диалог не найден")
                                        preview_appeared = False

                                except Exception as e:
                                    logger.error(f"Ошибка проверки превью: {e}")
                                    preview_appeared = False

                                logger.info(f"📊 Итог проверки превью: preview_appeared = {preview_appeared}")

                                # КРИТИЧЕСКИ ВАЖНО: Если превью НЕТ - НЕ продолжаем!
                                if not preview_appeared:
                                    logger.error("❌ Превью видео не появилось - файл не был загружен!")
                                    logger.error("❌ Останавливаем процесс публикации")

                                    # Делаем финальный скриншот
                                    try:
                                        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                                        screenshot_path = f"/tmp/instagram_failed_{timestamp}.png"
                                        self.browser.page.screenshot(path=screenshot_path, full_page=True)
                                        logger.info(f"📸 Финальный скриншот ошибки: {screenshot_path}")
                                    except:
                                        pass

                                    uploaded = False
                                    result['error'] = "Файл не был загружен - превью не появилось"
                                    return result

                                logger.info("✅ Превью подтверждено, продолжаем...")
                                
                                # После загрузки через filechooser, сразу обрабатываем превью
                                logger.info("🔍 Проверяем появление превью после загрузки через filechooser...")
                                preview_appeared = False
                                try:
                                    # Ждем появления превью видео
                                    preview_elem = self.browser.page.wait_for_selector(
                                        'video, img[src*="blob"], canvas, [aria-label*="Video"], [aria-label*="video"]',
                                        timeout=30000,
                                        state='visible'
                                    )
                                    if preview_elem and preview_elem.is_visible():
                                        logger.info("✅ Видео обработано, превью появилось и действительно видно")
                                        preview_appeared = True
                                    else:
                                        logger.warning("⚠️ Найден элемент превью через wait_for_selector, но он невидим")
                                except Exception as preview_e:
                                    logger.warning(f"⚠️ Не удалось дождаться превью видео: {preview_e}")
                                    # Проверяем, может превью уже есть
                                    try:
                                        preview_elem = self.browser.page.query_selector('video, img[src*="blob"], canvas')
                                        if preview_elem and preview_elem.is_visible():
                                            logger.info("✅ Превью найдено через query_selector и действительно видно")
                                            preview_appeared = True
                                        elif preview_elem:
                                            logger.warning("⚠️ Найден элемент превью через query_selector, но он невидим")
                                    except Exception as query_e:
                                        logger.debug(f"Ошибка при проверке превью через query_selector: {query_e}")
                                
                                # КРИТИЧЕСКИ ВАЖНО: Проверяем, что превью ДЕЙСТВИТЕЛЬНО видно
                                logger.info("🔍 Дополнительная проверка: превью действительно видно?")
                                try:
                                    video_elem = self.browser.page.query_selector('video')
                                    if video_elem:
                                        is_visible = video_elem.is_visible()
                                        rect = video_elem.bounding_box()
                                        logger.info(f"📊 video элемент: visible={is_visible}, size={rect['width'] if rect else 0}x{rect['height'] if rect else 0}")

                                        if is_visible and rect and rect['width'] > 0 and rect['height'] > 0:
                                            logger.info("✅ Видео обработано, превью появилось и действительно видно")
                                            preview_appeared = True
                                        else:
                                            logger.warning("⚠️ video элемент найден, но не виден или имеет нулевой размер")
                                            preview_appeared = False
                                    else:
                                        logger.warning("⚠️ video элемент не найден")
                                        preview_appeared = False
                                except Exception as e:
                                    logger.warning(f"Ошибка проверки превью: {e}")
                                    preview_appeared = False

                                # После появления превью нужно кликнуть на кнопку "Далее" несколько раз
                                # Этап 1: Экран "Обрезать" -> клик "Далее"
                                # Этап 2: Экран "Редактировать" -> клик "Далее"
                                # Этап 3: Экран "Создание публикации" -> добавление подписи -> клик "Поделиться"
                                if preview_appeared:
                                    logger.info("🔍 Превью появилось, ищем кнопку 'Далее' для перехода к редактированию...")
                                    
                                    # Функция для поиска и клика на кнопку "Далее" с использованием разных селекторов
                                    def click_next_button():
                                        """Ищет и кликает на кнопку 'Далее' используя различные селекторы"""
                                        selectors = [
                                            'div[data-cursor-element-id]:has-text("Далее")',
                                            'div:has-text("Далее"):not([aria-label])',
                                            'text=/^Далее$/i',
                                            'button:has-text("Далее")',
                                            '[aria-label*="Далее"]',
                                            'text=/^Next$/i',
                                            'button:has-text("Next")',
                                        ]
                                        
                                        for selector in selectors:
                                            try:
                                                next_button = self.browser.page.query_selector(selector)
                                                if next_button:
                                                    # Проверяем, что элемент видим
                                                    if next_button.is_visible():
                                                        logger.info(f"✅ Найдена кнопка 'Далее' через селектор: {selector}")
                                                        try:
                                                            # Используем JavaScript клик для надежности
                                                            self.browser.page.evaluate('''(elem) => {
                                                                elem.click();
                                                            }''', next_button)
                                                            logger.info("✅ Клик на 'Далее' выполнен")
                                                            return True
                                                        except Exception as click_e:
                                                            logger.debug(f"⚠️ Ошибка при клике через JS: {click_e}, пробуем обычный клик...")
                                                            try:
                                                                next_button.click(timeout=3000)
                                                                logger.info("✅ Клик на 'Далее' выполнен (обычный клик)")
                                                                return True
                                                            except:
                                                                pass
                                            except:
                                                continue
                                        return False
                                    
                                    # НОВЫЙ ПОДХОД: Используем JavaScript для поиска и клика по кнопкам "Далее"
                                    # Это более надежно, так как работает напрямую с DOM
                                    logger.info("📌 Используем JavaScript для поиска и клика по кнопкам 'Далее'...")
                                    
                                    def click_next_in_dialog():
                                        """
                                        Ищет и кликает на кнопку 'Далее' ТОЛЬКО внутри диалога создания публикации
                                        Это критически важно - иначе может кликнуть на "Далее" в историях или карусели
                                        """
                                        result = self.browser.page.evaluate('''() => {
                                            // Сначала находим диалог создания публикации
                                            const dialogs = Array.from(document.querySelectorAll('div[role="dialog"]'));

                                            // Ищем диалог с контентом (не пустой)
                                            let targetDialog = null;
                                            for (let dialog of dialogs) {
                                                const rect = dialog.getBoundingClientRect();
                                                // Диалог должен быть большим (более 300px) и видимым
                                                if (rect.width > 300 && rect.height > 300 &&
                                                    window.getComputedStyle(dialog).display !== 'none') {
                                                    targetDialog = dialog;
                                                    break;
                                                }
                                            }

                                            if (!targetDialog) {
                                                return {success: false, error: 'Диалог не найден'};
                                            }

                                            // Теперь ищем кнопку "Далее" ТОЛЬКО внутри этого диалога
                                            const allElements = Array.from(targetDialog.querySelectorAll('*'));

                                            for (let elem of allElements) {
                                                const text = (elem.textContent || '').trim();
                                                const ariaLabel = elem.getAttribute('aria-label') || '';

                                                // Проверяем ТОЧНОЕ совпадение текста
                                                const isNextButton = (text === 'Далее' || text === 'Next');

                                                if (isNextButton) {
                                                    const rect = elem.getBoundingClientRect();

                                                    // Проверяем, что элемент видим и это небольшая кнопка
                                                    if (rect.width > 0 && rect.height > 0 &&
                                                        rect.height < 200 &&
                                                        window.getComputedStyle(elem).display !== 'none' &&
                                                        window.getComputedStyle(elem).visibility !== 'hidden') {

                                                        elem.click();
                                                        return {
                                                            success: true,
                                                            text: text,
                                                            ariaLabel: ariaLabel,
                                                            width: rect.width,
                                                            height: rect.height
                                                        };
                                                    }
                                                }
                                            }

                                            return {success: false, error: 'Кнопка "Далее" не найдена внутри диалога'};
                                        }''')

                                        if result and result.get('success'):
                                            logger.info(f"✅ Кликнута кнопка 'Далее' внутри диалога: text='{result.get('text')}', size={result.get('width')}x{result.get('height')}")
                                            return True
                                        else:
                                            error = result.get('error') if result else 'Unknown error'
                                            logger.warning(f"⚠️ Не удалось кликнуть 'Далее': {error}")
                                            return False
                                    
                                    # Этап 1: Клик на первую кнопку "Далее" (экран "Обрезать")
                                    logger.info("📌 Этап 1: Ищем первую кнопку 'Далее' (экран 'Обрезать')...")
                                    if click_next_in_dialog():
                                        logger.info("✅ Первая кнопка 'Далее' кликнута")
                                        self.browser.random_delay(5, 7)

                                        # Проверяем, что перешли на следующий экран
                                        logger.info("🔍 Проверяем переход на экран редактирования...")
                                        try:
                                            # Ждем появления индикаторов экрана редактирования
                                            edit_indicators = self.browser.page.query_selector_all(
                                                'text=/Редактировать|Edit|Фильтры|Filters/i'
                                            )
                                            if len(edit_indicators) > 0:
                                                logger.info(f"✅ Переход подтвержден, найдено {len(edit_indicators)} индикаторов редактирования")
                                            else:
                                                logger.warning("⚠️ Индикаторы экрана редактирования не найдены")
                                        except Exception as e:
                                            logger.debug(f"Ошибка проверки перехода: {e}")

                                        # Этап 2: Клик на вторую кнопку "Далее" (экран "Редактировать")
                                        logger.info("📌 Этап 2: Ищем вторую кнопку 'Далее' (экран 'Редактировать')...")
                                        if click_next_in_dialog():
                                            logger.info("✅ Вторая кнопка 'Далее' кликнута")
                                            self.browser.random_delay(5, 7)

                                            # Ждем загрузки финального экрана
                                            logger.info("⏳ Ждем загрузки финального экрана...")
                                            try:
                                                self.browser.page.wait_for_load_state('networkidle', timeout=10000)
                                                logger.info("✅ Финальный экран загружен (networkidle)")
                                            except:
                                                logger.info("⚠️ networkidle не достигнут, но продолжаем")

                                            # Проверяем URL - должен измениться
                                            current_url = self.browser.page.url
                                            logger.info(f"📍 URL после второго 'Далее': {current_url}")

                                            if '/create/' in current_url or 'Поделиться' in self.browser.page.content():
                                                logger.info("✅ Успешно перешли на экран создания публикации!")
                                            else:
                                                logger.warning(f"⚠️ Возможно, не перешли на финальный экран. URL: {current_url}")
                                        else:
                                            logger.error("❌ Не удалось найти вторую кнопку 'Далее'")
                                    else:
                                        logger.error("❌ Не удалось найти первую кнопку 'Далее'")
                                        # Fallback на старый метод
                                        if click_next_button():
                                            self.browser.random_delay(3, 4)
                                            if click_next_button():
                                                self.browser.random_delay(3, 4)
                                                logger.info("✅ Успешно перешли на экран создания публикации (старый метод)!")
                                    
                                    # Проверяем, что мы на экране создания публикации
                                    logger.info("🔍 Проверяем текущий экран...")
                                    on_caption_screen = False

                                    try:
                                        # КРИТИЧЕСКИ ВАЖНО: Проверяем в правильном порядке

                                        # 1. Сначала проверяем, что НЕ на экранах редактирования
                                        edit_screen_indicators = [
                                            'text=/^Обрезать$|^Crop$/i',
                                            'text=/^Редактировать$|^Edit$/i',
                                            'text=/^Фильтры$|^Filters$/i',
                                        ]

                                        is_on_edit_screen = False
                                        for selector in edit_screen_indicators:
                                            try:
                                                elem = self.browser.page.query_selector(selector)
                                                if elem and elem.is_visible():
                                                    logger.info(f"⚠️ Еще на экране редактирования (найден: {selector})")
                                                    is_on_edit_screen = True
                                                    break
                                            except:
                                                pass

                                        if not is_on_edit_screen:
                                            # ДОБАВЛЯЕМ: Ждем немного, чтобы страница загрузилась
                                            self.browser.random_delay(2, 3)

                                            # 2. Проверяем наличие ВИДИМОГО поля для подписи
                                            caption_field_selectors = [
                                                '[aria-label="Добавьте подпись…"]',
                                                '[aria-label*="Добавьте подпись"]',
                                                '[aria-label*="Write a caption"]',
                                                '[aria-placeholder*="Добавьте подпись"]',
                                                '[aria-placeholder*="Write a caption"]',
                                                '[contenteditable="true"]',  # Любое редактируемое поле
                                                'div[role="textbox"]',       # Элементы с ролью textbox
                                                'textarea',                   # Обычные textarea
                                            ]

                                            caption_field_found = False
                                            for selector in caption_field_selectors:
                                                try:
                                                    elem = self.browser.page.query_selector(selector)
                                                    if elem and elem.is_visible():
                                                        logger.info(f"✅ Найдено видимое поле для подписи: {selector}")
                                                        caption_field_found = True
                                                        break
                                                except:
                                                    pass

                                            # 3. Проверяем наличие кнопки "Поделиться"
                                            share_button_found = False
                                            share_selectors = [
                                                'text=/^Поделиться$|^Share$/i',
                                                'button:has-text("Поделиться")',
                                                'button:has-text("Share")',
                                                '[aria-label*="Поделиться"]',
                                                '[aria-label*="Share"]',
                                                'div:has-text("Поделиться")',
                                                'div:has-text("Share")',
                                            ]

                                            for selector in share_selectors:
                                                try:
                                                    elem = self.browser.page.query_selector(selector)
                                                    if elem and elem.is_visible():
                                                        logger.info(f"✅ Найдена кнопка 'Поделиться': {selector}")
                                                        share_button_found = True
                                                        break
                                                except:
                                                    pass

                                            # 4. ДОБАВЛЯЕМ: Проверяем наличие других элементов создания публикации
                                            other_create_elements = False
                                            create_selectors = [
                                                'text=/^Ваша история$|^Your story$/i',  # Опция "Ваша история"
                                                'text=/^Дополнительные параметры$|^Advanced settings$/i',
                                                '[aria-label*="История"]',  # Story related
                                                '[aria-label*="Story"]',
                                                'input[type="checkbox"]',   # Чекбоксы настроек
                                            ]

                                            for selector in create_selectors:
                                                try:
                                                    elem = self.browser.page.query_selector(selector)
                                                    if elem and elem.is_visible():
                                                        logger.info(f"✅ Найден элемент создания публикации: {selector}")
                                                        other_create_elements = True
                                                        break
                                                except:
                                                    pass

                                            # Проверяем URL (должен остаться /create/... или измениться)
                                            current_url = self.browser.page.url
                                            logger.info(f"📍 Текущий URL: {current_url}")

                                            # ДОБАВЛЯЕМ: Проверяем, есть ли мы все еще в диалоге создания
                                            in_create_dialog = False
                                            dialog_selectors = [
                                                '[role="dialog"][aria-label*="Создание"]',
                                                '[role="dialog"][aria-label*="Create"]',
                                                'div[data-testid*="creation-modal"]',
                                                'div[role="dialog"]',  # Любой диалог
                                            ]

                                            for selector in dialog_selectors:
                                                try:
                                                    elem = self.browser.page.query_selector(selector)
                                                    if elem and elem.is_visible():
                                                        logger.info(f"✅ Находимся в диалоге создания: {selector}")
                                                        in_create_dialog = True
                                                        break
                                                except:
                                                    pass

                                            # ========================================
                                            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Правильное определение экрана
                                            # ========================================
                                            # КРИТИЧЕСКИ ВАЖНО: Правильный порядок проверки экранов
                                            # 1. Экран загрузки: есть "Перетащите сюда"
                                            # 2. Экран редактирования: есть опции размера (9:16, 16:9)
                                            # 3. Финальный экран: есть "Поделиться" И поле для подписи

                                            # 1. Проверяем экран ЗАГРУЗКИ (самый первый)
                                            upload_screen = self.browser.page.query_selector('text=/Перетащите сюда фото и видео|Выбрать на компьютере/i')
                                            if upload_screen and upload_screen.is_visible():
                                                logger.info("📍 На экране загрузки файла")
                                                on_caption_screen = False
                                            else:
                                                # 2. Проверяем экран ОБРЕЗКИ/РЕДАКТИРОВАНИЯ (есть опции размера)
                                                size_options = self.browser.page.query_selector_all('text=/9:16|16:9|1:1|4:5|Оригинал|Original/i')
                                                edit_indicators = self.browser.page.query_selector('text=/Обрезать|Crop|Редактировать|Edit|Фильтры|Filters/i')

                                                if len(size_options) > 0 or edit_indicators:
                                                    logger.info(f"📍 На экране редактирования (найдено элементов размера: {len(size_options)})")
                                                    on_caption_screen = False
                                                else:
                                                    # 3. Проверяем ФИНАЛЬНЫЙ экран (есть кнопка "Поделиться" И поле для подписи)
                                                    share_button = self.browser.page.query_selector('text=/^Поделиться$|^Share$/i')
                                                    caption_field = self.browser.page.query_selector('[aria-label*="Добавьте подпись"], [aria-label*="Write a caption"], [contenteditable="true"]')

                                                    # КРИТИЧЕСКИ ВАЖНО: Оба элемента должны быть ВИДИМЫ
                                                    share_visible = share_button and share_button.is_visible() if share_button else False
                                                    caption_visible = caption_field and caption_field.is_visible() if caption_field else False

                                                    if share_visible and caption_visible:
                                                        logger.info("✅ На ФИНАЛЬНОМ экране создания публикации!")
                                                        on_caption_screen = True
                                                    elif share_visible or caption_visible:
                                                        logger.info(f"📍 Возможно на финальном экране (share_visible={share_visible}, caption_visible={caption_visible})")
                                                        on_caption_screen = True
                                                    else:
                                                        logger.info("📍 Экран не определен, продолжаем обычный процесс")
                                                        on_caption_screen = False
                                                logger.info("🔍 Расширенная диагностика:")

                                                # Логируем все видимые элементы с aria-label
                                                try:
                                                    all_labeled = self.browser.page.query_selector_all('[aria-label], [aria-placeholder]')
                                                    visible_labels = []
                                                    for elem in all_labeled[:30]:
                                                        try:
                                                            if elem.is_visible():
                                                                label = elem.get_attribute('aria-label') or elem.get_attribute('aria-placeholder') or ''
                                                                if label and len(label.strip()) > 0:
                                                                    visible_labels.append(label[:60])
                                                        except:
                                                            pass
                                                    if visible_labels:
                                                        logger.info(f"📋 Видимые aria-label/placeholder: {visible_labels[:15]}")
                                                except:
                                                    pass

                                                # Логируем все видимые кнопки
                                                try:
                                                    all_buttons = self.browser.page.query_selector_all('button, [role="button"], input[type="button"]')
                                                    visible_buttons = []
                                                    for elem in all_buttons[:20]:
                                                        try:
                                                            if elem.is_visible():
                                                                text = elem.text_content() or elem.get_attribute('aria-label') or ''
                                                                if text and len(text.strip()) > 0:
                                                                    visible_buttons.append(text[:40])
                                                        except:
                                                            pass
                                                    if visible_buttons:
                                                        logger.info(f"📋 Видимые кнопки: {visible_buttons[:10]}")
                                                except:
                                                    pass

                                    except Exception as e:
                                        logger.error(f"Ошибка при проверке экрана: {e}")
                                    
                                    # ========================================
                                    # КРИТИЧЕСКИ ВАЖНО: НЕ устанавливаем skip_intermediate_steps = True здесь!
                                    # Экран редактирования (с элементами размера) НЕ является финальным экраном!
                                    # ========================================
                                    if on_caption_screen:
                                        logger.info("✅ Перешли на финальный экран создания публикации")
                                        uploaded = True
                                        video_loaded = True
                                        # skip_intermediate_steps устанавливаем ТОЛЬКО на финальном экране
                                    else:
                                        logger.info("📍 На экране редактирования, продолжаем обычный процесс")
                                        skip_intermediate_steps = False
                            else:
                                logger.warning("⚠️ Кнопка 'Выбрать на компьютере' не найдена, пробуем программную установку...")
                                
                                # Fallback: программная установка через set_input_files
                                if file_inputs:
                                    for i, input_elem in enumerate(file_inputs):
                                        try:
                                            logger.info(f"📤 Способ fallback: Устанавливаем файл в input[type='file'][{i}] через set_input_files...")
                                            input_locator = self.browser.page.locator('input[type="file"]').nth(i)
                                            input_locator.set_input_files(video_path)
                                            logger.info("✅ set_input_files выполнен")
                                            
                                            # Триггерим событие change
                                            self.browser.page.evaluate('''(input) => {
                                                const changeEvent = new Event('change', { bubbles: true, cancelable: true });
                                                input.dispatchEvent(changeEvent);
                                            }''', input_elem)
                                            
                                            self.browser.random_delay(3, 5)
                                            
                                            # Проверяем, что файл установлен
                                            files_count = self.browser.page.evaluate('''(input) => {
                                                return input.files ? input.files.length : 0;
                                            }''', input_elem)
                                            
                                            if files_count > 0:
                                                logger.info("✅ Файл успешно установлен через set_input_files!")
                                                uploaded = True
                                                break
                                        except Exception as e:
                                            logger.warning(f"⚠️ Ошибка при установке файла в input[{i}]: {e}")
                        except Exception as filechooser_e:
                            logger.warning(f"⚠️ Filechooser не сработал: {filechooser_e}")
                            logger.info("📤 Пробуем программную установку через set_input_files...")
                            
                            # Fallback: программная установка
                            if file_inputs:
                                for i, input_elem in enumerate(file_inputs):
                                    try:
                                        input_locator = self.browser.page.locator('input[type="file"]').nth(i)
                                        input_locator.set_input_files(video_path)
                                        self.browser.page.evaluate('''(input) => {
                                            const changeEvent = new Event('change', { bubbles: true, cancelable: true });
                                            input.dispatchEvent(changeEvent);
                                        }''', input_elem)
                                        self.browser.random_delay(3, 5)
                                        
                                        files_count = self.browser.page.evaluate('''(input) => {
                                            return input.files ? input.files.length : 0;
                                        }''', input_elem)
                                        
                                        if files_count > 0:
                                            uploaded = True
                                            break
                                    except:
                                        pass
                                
                                # Если файл загружен через fallback, продолжаем обработку
                                # КРИТИЧЕСКИ ВАЖНО: Пропускаем этот блок, если уже перешли на финальный экран через filechooser
                                if uploaded and not skip_intermediate_steps:
                                    logger.info("✅ Файл установлен через set_input_files, ждем обработки Instagram...")
                                    
                                    # КРИТИЧЕСКИ ВАЖНО: Ждем обработки файла Instagram (появления превью)
                                    logger.info("⏳ Ожидание обработки видео Instagram (появление превью, до 30 секунд)...")
                                    preview_appeared = False
                                    try:
                                        # Ждем появления превью видео или индикаторов обработки
                                        preview_elem = self.browser.page.wait_for_selector(
                                            'video, img[src*="blob"], canvas, [aria-label*="Video"], [aria-label*="video"]',
                                            timeout=30000,
                                            state='visible'
                                        )
                                        if preview_elem and preview_elem.is_visible():
                                            logger.info("✅ Видео обработано, превью появилось и действительно видно")
                                            preview_appeared = True
                                        else:
                                            logger.warning("⚠️ Найден элемент превью, но он невидим")
                                    except Exception as preview_e:
                                        logger.warning(f"⚠️ Не удалось дождаться превью видео: {preview_e}")
                                        # Проверяем, может превью уже есть
                                        try:
                                            preview_elem = self.browser.page.query_selector('video, img[src*="blob"], canvas')
                                            if preview_elem and preview_elem.is_visible():
                                                logger.info("✅ Превью найдено через query_selector и действительно видно")
                                                preview_appeared = True
                                            elif preview_elem:
                                                logger.warning("⚠️ Найден элемент превью через query_selector, но он невидим")
                                        except Exception as query_e:
                                            logger.debug(f"Ошибка при проверке превью через query_selector: {query_e}")
                                    
                                    if not preview_appeared:
                                        logger.warning("⚠️ Превью не появилось, но продолжаем...")
                                        # Логируем все найденные элементы превью для отладки
                                        try:
                                            all_preview_elements = self.browser.page.query_selector_all('video, img[src*="blob"], canvas, [aria-label*="Video"], [aria-label*="video"]')
                                            logger.info(f"📊 Всего найдено потенциальных элементов превью: {len(all_preview_elements)}")
                                            for i, elem in enumerate(all_preview_elements[:10]):  # Ограничим до 10 элементов
                                                try:
                                                    tag_name = elem.tag_name
                                                    aria_label = elem.get_attribute('aria-label') or ''
                                                    src = elem.get_attribute('src') or ''
                                                    is_visible = elem.is_visible()
                                                    logger.info(f"  [{i}] {tag_name}: aria-label='{aria_label}', src='{src[:50]}...', visible={is_visible}")
                                                except Exception as log_e:
                                                    logger.debug(f"Ошибка при логировании элемента {i}: {log_e}")
                                        except Exception as log_e:
                                            logger.warning(f"Ошибка при логировании элементов превью: {log_e}")
                                    
                                    # КРИТИЧЕСКИ ВАЖНО: После появления превью Instagram может требовать дополнительного действия
                                    # Проверяем, есть ли кнопка "Далее" или другие элементы для перехода
                                    if preview_appeared:
                                        logger.info("🔍 Превью появилось, проверяем наличие кнопок для перехода...")
                                        try:
                                            # Ищем кнопку "Далее" или другие элементы редактирования
                                            next_button = self.browser.page.query_selector('text=/^Далее$|^Next$/i')
                                            if not next_button:
                                                next_button = self.browser.page.query_selector('button:has-text("Далее"), button:has-text("Next")')
                                            size_options = self.browser.page.query_selector('text=/9:16|16:9|1:1|Оригинал|Original/i')
                                            
                                            if next_button:
                                                logger.info("✅ Найдена кнопка 'Далее', возможно нужно кликнуть...")
                                                try:
                                                    next_button.click(timeout=3000)
                                                    logger.info("✅ Клик на 'Далее' выполнен")
                                                    self.browser.random_delay(2, 3)
                                                except:
                                                    pass
                                            
                                            if size_options:
                                                logger.info("✅ Найдены опции размера, переходим к выбору размера...")
                                        except:
                                            pass
                                    
                                    # КРИТИЧЕСКИ ВАЖНО: Проверяем реальное состояние экрана
                                    # Возможно, Instagram уже обработал файл, но экран загрузки все еще виден
                                    logger.info("🔍 Проверяем реальное состояние экрана после установки файла...")
                                    transition_complete = False
                                    try:
                                        # Проверяем наличие элементов редактирования (размер, обрезка и т.д.)
                                        size_options = self.browser.page.query_selector_all('text=/9:16|16:9|1:1|Оригинал|Original/i')
                                        next_button = self.browser.page.query_selector_all('text=/^Далее$|^Next$/i')
                                        if len(next_button) == 0:
                                            next_button = self.browser.page.query_selector_all('button:has-text("Далее"), button:has-text("Next")')
                                        video_preview = self.browser.page.query_selector('video, [class*="preview"], [class*="video"]')

                                        logger.info(f"📊 Найдено элементов размера: {len(size_options)}")
                                        logger.info(f"📊 Найдено кнопок 'Далее': {len(next_button)}")
                                        logger.info(f"📊 Найдено превью видео: {video_preview is not None}")

                                        # Если есть элементы редактирования, значит переход уже произошел
                                        if len(size_options) > 0 or len(next_button) > 0:
                                            logger.info("✅ Элементы редактирования найдены! Переход уже произошел!")
                                            transition_complete = True
                                        else:
                                            logger.info("⏳ Элементы редактирования не найдены, ждем...")
                                    except Exception as e:
                                        logger.debug(f"Ошибка при проверке состояния: {e}")

                                    # КРИТИЧЕСКИ ВАЖНО: Ждем реального перехода на экран редактирования
                                    # Проверяем, что текст "Перетащите сюда фото и видео" ИСЧЕЗ
                                    if not transition_complete:
                                        logger.info("⏳ Ждем перехода на экран редактирования (исчезновение текста загрузки)...")
                                        max_wait_time = 15  # Уменьшаем до 15 секунд
                                        wait_interval = 2   # Проверяем каждые 2 секунды
                                        waited = 0
                                        
                                        while waited < max_wait_time and not transition_complete:
                                            try:
                                                # Проверяем наличие элементов редактирования (более надежный индикатор)
                                                size_options = self.browser.page.query_selector_all('text=/9:16|16:9|1:1|Оригинал|Original/i')
                                                next_button = self.browser.page.query_selector_all('text=/^Далее$|^Next$/i')
                                                if len(next_button) == 0:
                                                    next_button = self.browser.page.query_selector_all('button:has-text("Далее"), button:has-text("Next")')
                                                
                                                if len(size_options) > 0 or len(next_button) > 0:
                                                    logger.info("✅ Найдены элементы редактирования! Переход завершен!")
                                                    transition_complete = True
                                                    break
                                                
                                                # ГЛАВНАЯ ПРОВЕРКА: Текст загрузки должен ИСЧЕЗНУТЬ
                                                upload_text_locator = self.browser.page.locator(
                                                    'text=/Перетащите сюда фото и видео|Выбрать на компьютере|Drag photos and videos here|Select from computer/i'
                                                )
                                                
                                                # Проверяем видимость текста загрузки
                                                is_upload_text_visible = False
                                                try:
                                                    if upload_text_locator.count() > 0:
                                                        is_upload_text_visible = upload_text_locator.first.is_visible(timeout=1000)
                                                except:
                                                    pass
                                                
                                                logger.info(f"🔍 Проверка {waited}/{max_wait_time}с: Текст загрузки виден = {is_upload_text_visible}, Элементы редактирования = {len(size_options) + len(next_button)}")
                                                
                                                # Если текст загрузки исчез, проверяем наличие элементов редактирования
                                                if not is_upload_text_visible:
                                                    logger.info("✅ Текст загрузки исчез! Проверяем наличие элементов редактирования...")
                                                    
                                                    if len(size_options) > 0 or len(next_button) > 0:
                                                        logger.info("✅ Найдены элементы редактирования! Переход завершен!")
                                                        transition_complete = True
                                                        break
                                                    else:
                                                        logger.debug("⏳ Элементы редактирования еще не появились, ждем...")
                                                
                                                self.browser.random_delay(wait_interval, wait_interval + 1)
                                                waited += wait_interval
                                                
                                            except Exception as e:
                                                logger.debug(f"Ошибка при проверке перехода: {e}")
                                                self.browser.random_delay(1, 2)
                                                waited += 2
                                    
                                    if not transition_complete:
                                        # Финальная проверка состояния экрана
                                        logger.warning("⚠️ Не удалось дождаться перехода, проверяем финальное состояние...")
                                        
                                        # Проверяем наличие элементов редактирования (более надежный индикатор)
                                        final_size_options = self.browser.page.query_selector_all('text=/9:16|16:9|1:1|Оригинал|Original/i')
                                        final_next_button = self.browser.page.query_selector_all('text=/^Далее$|^Next$/i')
                                        if len(final_next_button) == 0:
                                            final_next_button = self.browser.page.query_selector_all('button:has-text("Далее"), button:has-text("Next")')
                                        
                                        if len(final_size_options) > 0 or len(final_next_button) > 0:
                                            logger.info("✅ Элементы редактирования найдены! Переход произошел!")
                                            transition_complete = True
                                        else:
                                            final_upload_text = self.browser.page.query_selector(
                                                'text=/Перетащите сюда фото и видео|Выбрать на компьютере/i'
                                            )
                                            if final_upload_text:
                                                logger.error("❌ ВСЕ ЕЩЕ НА ЭКРАНЕ ЗАГРУЗКИ! Файл не был загружен!")
                                                uploaded = False
                                            else:
                                                logger.warning("⚠️ Текст загрузки исчез, но элементы редактирования не найдены, продолжаем...")
                                    
                                    # Дополнительная задержка для стабилизации интерфейса
                                    if transition_complete:
                                        logger.info("⏳ Ждем стабилизации интерфейса (3-5 секунд)...")
                                        self.browser.random_delay(3, 5)
                                    
                        # Если файл загружен через filechooser, обрабатываем его
                        # КРИТИЧЕСКИ ВАЖНО: Пропускаем этот блок, если уже перешли на финальный экран
                        if uploaded and not skip_intermediate_steps:
                            logger.info("✅ Файл установлен через filechooser, ждем обработки Instagram...")
                            
                            # КРИТИЧЕСКИ ВАЖНО: Ждем обработки файла Instagram (появления превью)
                            logger.info("⏳ Ожидание обработки видео Instagram (появление превью, до 30 секунд)...")
                            preview_appeared = False
                            try:
                                # Ждем появления превью видео или индикаторов обработки
                                self.browser.page.wait_for_selector(
                                    'video, img[src*="blob"], canvas, [aria-label*="Video"], [aria-label*="video"]',
                                    timeout=30000,
                                    state='visible'
                                )
                                logger.info("✅ Видео обработано, превью появилось")
                                preview_appeared = True
                            except Exception as preview_e:
                                logger.warning(f"⚠️ Не удалось дождаться превью видео: {preview_e}")
                                # Проверяем, может превью уже есть
                                try:
                                    preview_elem = self.browser.page.query_selector('video, img[src*="blob"], canvas')
                                    if preview_elem:
                                        logger.info("✅ Превью найдено через query_selector")
                                        preview_appeared = True
                                except:
                                    pass
                        elif skip_intermediate_steps:
                            logger.info("⏭️ Пропускаем повторную обработку файла - уже на финальном экране")
                        else:
                            # Если input не найден, пробуем установить файл напрямую на диалог (drag-and-drop)
                            logger.warning("⚠️ input[type='file'] не найден, пробуем установить файл на диалог через drag-and-drop...")
                            try:
                                # Ищем диалог для установки файла
                                dialog_selectors = [
                                    'div[role="dialog"][aria-label*="Создание"]',
                                    'div[role="dialog"][aria-label*="Create"]',
                                    'div[role="dialog"]',
                                ]
                                
                                for selector in dialog_selectors:
                                    try:
                                        dialog_locator = self.browser.page.locator(selector).first
                                        if dialog_locator.is_visible(timeout=3000):
                                            logger.info(f"✅ Найден диалог: {selector}, устанавливаем файл через drag-and-drop...")
                                            # Устанавливаем файл на диалог (Playwright автоматически найдет input внутри)
                                            dialog_locator.set_input_files(video_path)
                                            logger.info("✅ Файл установлен на диалог")
                                            
                                            # Триггерим события drag-and-drop для обработки Instagram
                                            logger.info("🔄 Триггерим события drag-and-drop...")
                                            try:
                                                self.browser.page.evaluate('''(dialog) => {
                                                    // Триггерим события drag-and-drop
                                                    const dropEvent = new DragEvent('drop', { 
                                                        bubbles: true, 
                                                        cancelable: true,
                                                        dataTransfer: new DataTransfer()
                                                    });
                                                    dialog.dispatchEvent(dropEvent);
                                                    
                                                    // Также триггерим события для input внутри
                                                    const input = dialog.querySelector('input[type="file"]');
                                                    if (input) {
                                                        const changeEvent = new Event('change', { bubbles: true });
                                                        input.dispatchEvent(changeEvent);
                                                    }
                                                }''', dialog_locator)
                                                logger.info("✅ События drag-and-drop триггернуты")
                                            except Exception as trigger_e:
                                                logger.warning(f"⚠️ Не удалось триггернуть события: {trigger_e}")
                                            
                                            uploaded = True
                                            self.browser.random_delay(2, 3)
                                            break
                                    except Exception as e:
                                        logger.debug(f"Не удалось установить файл через {selector}: {e}")
                                        continue
                                
                                if not uploaded:
                                    logger.error("❌ Не удалось загрузить видео: input[type='file'] не найден и установка на диалог не сработала")
                            except Exception as drag_e:
                                logger.warning(f"Ошибка при установке файла на диалог: {drag_e}")
            except Exception as e:
                logger.error(f"Ошибка поиска input для загрузки видео: {e}", exc_info=True)
            
            if not uploaded:
                result['error'] = "Не удалось загрузить видео. input[type='file'] не найден в диалоге или не удалось установить файл"
                return result
            
            # Проверяем, что видео действительно загрузилось (есть превью или видео элемент)
            # КРИТИЧЕСКИ ВАЖНО: Пропускаем этот блок, если уже перешли на финальный экран через filechooser
            if not skip_intermediate_steps:
                logger.info("🔍 Проверка, что видео успешно загружено...")
                video_loaded = False
            else:
                logger.info("⏭️ Пропускаем проверку загрузки видео - уже на финальном экране")
                video_loaded = True
            try:
                if hasattr(self.browser, 'page') and self.browser.page:
                    # Проверяем наличие видео элемента или превью
                    video_selectors = ['video', 'img[src*="blob"]', 'canvas', '[aria-label*="Video"]']
                    for selector in video_selectors:
                        try:
                            video_elem = self.browser.page.query_selector(selector)
                            if video_elem and video_elem.is_visible():
                                logger.info(f"✅ Видео подтверждено (найден и видим элемент: {selector})")
                                video_loaded = True
                                break
                            elif video_elem:
                                logger.debug(f"Найден элемент {selector}, но он невидим")
                        except Exception as elem_e:
                            logger.debug(f"Ошибка при проверке элемента {selector}: {elem_e}")
                            continue
            except Exception as e:
                logger.warning(f"Ошибка при проверке загрузки видео: {e}")
            
            if not video_loaded:
                logger.warning("⚠️ Не удалось подтвердить загрузку видео, но продолжаем...")
            
            # Шаг 4: После загрузки видео Instagram показывает экран редактирования с опциями размера
            # Дополнительная проверка и ожидание перехода на экран редактирования
            # КРИТИЧЕСКИ ВАЖНО: Пропускаем этот блок, если уже перешли на финальный экран
            if not skip_intermediate_steps:
                logger.info("🔍 Проверяем текущий экран после загрузки видео...")
                try:
                    if hasattr(self.browser, 'page') and self.browser.page:
                        # Проверяем, что мы не на экране загрузки
                        upload_text = self.browser.page.query_selector('text=/Перетащите сюда фото и видео|Выбрать на компьютере/i')
                        if upload_text:
                            logger.warning("⚠️ Все еще на экране загрузки, ждем перехода...")
                            # Дополнительное ожидание с проверками
                            for attempt in range(5):  # 5 попыток по 3 секунды = 15 секунд
                                self.browser.random_delay(3, 3)
                                upload_text = self.browser.page.query_selector('text=/Перетащите сюда фото и видео|Выбрать на компьютере/i')
                                if not upload_text:
                                    logger.info("✅ Экран загрузки исчез, перешли к редактированию")
                                    break
                                logger.debug(f"⏳ Попытка {attempt + 1}/5: все еще на экране загрузки...")
                except Exception as e:
                    logger.debug(f"Ошибка при проверке экрана: {e}")
            else:
                logger.info("⏭️ Пропускаем проверку экрана - уже на финальном экране")
            
            # ========================================
            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Правильная проверка экрана ПЕРЕД каждым кликом "Далее"
            # ========================================
            # Проверяем, не находимся ли мы уже на экране создания публикации (после кликов на "Далее")
            skip_intermediate_steps = False
            try:
                if hasattr(self.browser, 'page') and self.browser.page:
                    # КРИТИЧЕСКИ ВАЖНО: Правильный порядок проверки экранов

                    # 1. Проверяем экран ЗАГРУЗКИ (самый первый)
                    upload_screen = self.browser.page.query_selector('text=/Перетащите сюда фото и видео|Выбрать на компьютере/i')
                    if upload_screen and upload_screen.is_visible():
                        logger.info("📍 На экране загрузки файла")
                        skip_intermediate_steps = False
                    else:
                        # 2. Проверяем экран ОБРЕЗКИ/РЕДАКТИРОВАНИЯ (есть опции размера)
                        size_options = self.browser.page.query_selector_all('text=/9:16|16:9|1:1|4:5|Оригинал|Original/i')
                        edit_indicators = self.browser.page.query_selector('text=/Обрезать|Crop|Редактировать|Edit|Фильтры|Filters/i')

                        if len(size_options) > 0 or edit_indicators:
                            logger.info(f"📍 На экране редактирования (найдено элементов размера: {len(size_options)})")
                            skip_intermediate_steps = False
                        else:
                            # 3. Проверяем ФИНАЛЬНЫЙ экран (есть кнопка "Поделиться" И поле для подписи)
                            share_button = self.browser.page.query_selector('text=/^Поделиться$|^Share$/i')
                            caption_field = self.browser.page.query_selector('[aria-label*="Добавьте подпись"], [aria-label*="Write a caption"], [contenteditable="true"]')

                            # КРИТИЧЕСКИ ВАЖНО: Оба элемента должны быть ВИДИМЫ
                            share_visible = share_button and share_button.is_visible() if share_button else False
                            caption_visible = caption_field and caption_field.is_visible() if caption_field else False

                            if share_visible and caption_visible:
                                logger.info("✅ На ФИНАЛЬНОМ экране создания публикации!")
                                skip_intermediate_steps = True
                            elif share_visible or caption_visible:
                                logger.info(f"📍 Возможно на финальном экране (share_visible={share_visible}, caption_visible={caption_visible})")
                                skip_intermediate_steps = True
                            else:
                                logger.info("📍 Экран не определен, продолжаем обычный процесс")
                                skip_intermediate_steps = False
            except Exception as e:
                logger.error(f"Ошибка определения экрана: {e}")
                skip_intermediate_steps = False

            logger.info(f"📊 Результат проверки: skip_intermediate_steps = {skip_intermediate_steps}")
            
            # Шаг 5: Выбираем размер 9:16 для Reels (только если видео загружено И мы еще не на экране создания публикации)
            if (video_loaded or uploaded) and not skip_intermediate_steps:
                logger.info("🔍 Выбираем размер 9:16 для Reels...")
                size_selected = False
                
                # Логируем текущее состояние страницы для отладки
                try:
                    if hasattr(self.browser, 'page') and self.browser.page:
                        current_url = self.browser.page.url
                        logger.info(f"📍 Текущий URL после загрузки видео: {current_url}")
                        
                        # Ищем все элементы с текстом, содержащим размеры
                        all_text_elements = self.browser.page.query_selector_all('div, span, button, a')
                        size_texts = []
                        for elem in all_text_elements[:200]:  # Первые 200 элементов
                            try:
                                text = (elem.inner_text() or elem.text_content() or '').strip()
                                if any(size in text for size in ['9:16', '16:9', '1:1', 'Оригинал', 'Original', 'Original', '4:5']):
                                    size_texts.append(text[:50])
                            except:
                                continue
                        if size_texts:
                            logger.info(f"📋 Найдены тексты с размерами на странице: {size_texts[:15]}")
                        else:
                            logger.warning("⚠️ Не найдено текстов с размерами на странице")
                            
                        # Логируем все видимые кнопки для отладки
                        visible_buttons = []
                        all_buttons = self.browser.page.query_selector_all('button, div[role="button"], a')
                        for btn in all_buttons[:50]:
                            try:
                                if btn.is_visible():
                                    text = (btn.inner_text() or btn.text_content() or '').strip()
                                    if text and len(text) < 30:
                                        visible_buttons.append(text)
                            except:
                                continue
                        if visible_buttons:
                            logger.info(f"📋 Видимые кнопки на странице: {visible_buttons[:20]}")
                except Exception as e:
                    logger.debug(f"Ошибка при логировании состояния: {e}")
                
                try:
                    if hasattr(self.browser, 'page') and self.browser.page:
                        # Ищем опцию "9:16" в селекторе размера - пробуем разные варианты
                        size_selectors = [
                            'text=/^9:16$/i',  # Точное совпадение
                            'text=/9:16/i',    # В любом месте
                            'div:has-text("9:16")',
                            'span:has-text("9:16")',
                            'button:has-text("9:16")',
                            '[aria-label*="9:16"]',
                            '[title*="9:16"]',
                        ]
                        
                        for selector in size_selectors:
                            try:
                                size_916_locator = self.browser.page.locator(selector).first
                                if size_916_locator.is_visible(timeout=3000):
                                    text = size_916_locator.inner_text() or size_916_locator.text_content() or ''
                                    logger.info(f"✅ Найдена опция '9:16' через селектор '{selector}', текст: '{text}', кликаем...")
                                    size_916_locator.click(timeout=5000)
                                    size_selected = True
                                    logger.info("✅ Размер 9:16 выбран, ждем обновления интерфейса...")
                                    self.browser.random_delay(3, 5)
                                    break
                            except:
                                continue
                        
                        # Если не нашли через селекторы, пробуем через data-cursor-element-id и поиск по тексту
                        if not size_selected:
                            try:
                                logger.info("🔍 Поиск размера 9:16 через перебор элементов...")
                                all_elements = self.browser.page.query_selector_all('div, span, button, a, [data-cursor-element-id]')
                                for elem in all_elements:
                                    try:
                                        text = (elem.inner_text() or elem.text_content() or '').strip()
                                        # Ищем точное совпадение "9:16" или элементы в списке размеров
                                        if text == '9:16' or (len(text) < 10 and '9:16' in text):
                                            # Проверяем, что это не слишком большой элемент (не контейнер)
                                            bounding_box = elem.bounding_box()
                                            if bounding_box and bounding_box['height'] < 100:
                                                logger.info(f"✅ Найдена опция '9:16' по тексту: '{text}', кликаем...")
                                                elem.click(timeout=5000)
                                                size_selected = True
                                                self.browser.random_delay(3, 5)
                                                break
                                    except:
                                        continue
                            except Exception as e:
                                logger.debug(f"Ошибка поиска размера через перебор: {e}")
                except Exception as e:
                    logger.warning(f"Не удалось выбрать размер 9:16: {e}")
                
                if not size_selected:
                    logger.warning("⚠️ Не удалось найти размер 9:16, возможно он уже выбран или недоступен, продолжаем...")
            else:
                logger.warning("⚠️ Видео не загружено, пропускаем выбор размера 9:16")
            
            # ========================================
            # ФИНАЛЬНАЯ ЛОГИКА: Обработка кликов "Далее"
            # ========================================

            # В блоке "Шаг 6: Нажимаем 'Далее'" убедитесь что проверяете skip_intermediate_steps:

            if not skip_intermediate_steps:
                logger.info("🔍 Начинаем процесс кликов 'Далее' (не на финальном экране)")
                max_next_clicks = 3

                for attempt in range(max_next_clicks):
                    logger.info(f"🔍 Ищем кнопку 'Далее' (попытка {attempt + 1}/{max_next_clicks})...")

                    # Проверяем текущий экран перед кликом
                    try:
                        dialog = self.browser.page.query_selector('div[role="dialog"]')
                        if dialog:
                            dialog_text = dialog.inner_text()
                            logger.info(f"📋 Текущий экран содержит: {dialog_text[:100]}")

                            # Если уже на финальном экране - прерываем
                            if 'Поделиться' in dialog_text or 'Share' in dialog_text:
                                logger.info("✅ Достигнут финальный экран, прерываем поиск 'Далее'")
                                skip_intermediate_steps = True
                                break
                    except:
                        pass

                    # Ищем и кликаем "Далее"
                    next_clicked = False
                    try:
                        next_selectors = [
                            'text=/^Далее$/i',
                            'text=/^Next$/i',
                            'button:has-text("Далее")',
                            'button:has-text("Next")',
                            '[aria-label*="Далее"]',
                            '[aria-label*="Next"]',
                        ]

                        for selector in next_selectors:
                            try:
                                next_elem = self.browser.page.query_selector(selector)
                                if next_elem and next_elem.is_visible():
                                    logger.info(f"✅ Найдена кнопка 'Далее': {selector}")
                                    next_elem.click(timeout=5000)
                                    next_clicked = True
                                    logger.info("✅ Клик на 'Далее' выполнен")
                                    self.browser.random_delay(5, 7)
                                    break
                            except:
                                continue
                    except Exception as e:
                        logger.warning(f"Ошибка при поиске 'Далее': {e}")

                    if not next_clicked:
                        logger.info(f"⚠️ Кнопка 'Далее' не найдена на попытке {attempt + 1}")
                        break

                # После всех кликов проверяем экран снова
                try:
                    dialog = self.browser.page.query_selector('div[role="dialog"]')
                    if dialog:
                        dialog_text = dialog.inner_text()
                        if 'Поделиться' in dialog_text or 'Share' in dialog_text:
                            logger.info("✅ Успешно достигнут финальный экран!")
                            skip_intermediate_steps = True
                        else:
                            logger.warning(f"⚠️ После кликов 'Далее' экран: {dialog_text[:100]}")
                except:
                    pass
            else:
                logger.info("⏭️ Пропускаем клики 'Далее' - уже на финальном экране")

            # Шаг 6: Добавляем подпись с хештегами - после выбора размера 9:16 и нажатия "Далее"
            # Если мы уже на экране создания публикации, ждем появления поля для подписи
            if skip_intermediate_steps:
                logger.info("⏳ Ждем появления поля для подписи на экране создания публикации (до 20 секунд)...")

                # Ждем загрузки React компонентов
                try:
                    self.browser.page.wait_for_load_state('domcontentloaded', timeout=5000)
                except:
                    pass

                # НОВЫЙ ПОДХОД: Используем JavaScript для поиска поля
                logger.info("🔍 Используем JavaScript для поиска поля подписи...")

                caption_field = None
                try:
                    # ДОБАВЛЯЕМ: Ждем немного перед поиском
                    self.browser.random_delay(1, 2)

                    # Простой поиск поля для подписи
                    caption_selectors = [
                        '[aria-label*="подпись"]',
                        '[aria-placeholder*="подпись"]',
                        '[contenteditable="true"]',
                        'textarea',
                        'input[type="text"]'
                    ]

                    for selector in caption_selectors:
                        try:
                            elem = self.browser.page.query_selector(selector)
                            if elem and elem.is_visible():
                                caption_field = elem
                                logger.info(f"✅ Найдено поле для подписи: {selector}")
                                break
                        except:
                            continue

                except Exception as e:
                    logger.warning(f"Ошибка поиска поля для подписи: {e}")

                self.browser.random_delay(2, 3)
            
            # Формируем полный текст: описание + хештеги
            full_caption = caption
            if hashtags:
                hashtags_text = ' '.join([f'#{tag}' if not tag.startswith('#') else tag for tag in hashtags])
                if full_caption:
                    full_caption = f"{full_caption}\n\n{hashtags_text}"
                else:
                    full_caption = hashtags_text
            
            if full_caption:
                logger.info("📝 Добавление подписи с хештегами...")
                try:
                    if hasattr(self.browser, 'page') and self.browser.page:
                        from playwright.sync_api import Page
                        if isinstance(self.browser.page, Page):
                            # Ждем загрузки React компонентов перед поиском поля
                            logger.info("⏳ Ждем загрузки React компонентов перед поиском поля подписи...")
                            try:
                                self.browser.page.wait_for_load_state('networkidle', timeout=5000)
                            except:
                                pass
                            
                            # Ищем поле подписи в десктопной версии с расширенным набором селекторов
                            caption_selectors = [
                                '[aria-label="Добавьте подпись…"]',
                                '[aria-placeholder="Добавьте подпись…"]',
                                '[aria-label*="Добавьте подпись"]',
                                '[aria-placeholder*="Добавьте подпись"]',
                                'div[contenteditable="true"][role="textbox"]',
                                'div[contenteditable="true"][aria-label*="Добавьте подпись"]',
                                'div[contenteditable="true"][aria-label*="Add a caption"]',
                                'div[contenteditable="true"][aria-placeholder*="Добавьте подпись"]',
                                'div[contenteditable="true"][aria-placeholder*="Add a caption"]',
                                'div[contenteditable="true"][data-lexical-editor="true"]',
                                '[contenteditable="true"][aria-label*="подпись"]',
                                '[contenteditable="true"][aria-label*="caption"]',
                                '[aria-label*="Write a caption"]',
                                'textarea[aria-label*="Добавьте подпись"]',
                                'textarea[aria-label*="Add a caption"]',
                                'textarea[aria-label*="Write a caption"]',
                                'textarea[placeholder*="Write a caption"]',
                            ]
                            
                            # Используем уже найденное поле caption_field из предыдущего блока
                            caption_added = False
                            if caption_field:
                                logger.info("✅ Используем найденное поле для подписи")
                                try:
                                    # Фокусируемся на поле
                                    caption_field.click()
                                    self.browser.random_delay(0.5, 1)
                                    # Очищаем поле и вводим текст
                                    caption_field.fill('')
                                    self.browser.random_delay(0.5, 1)
                                    caption_field.type(full_caption, delay=50)
                                    caption_added = True
                                    self.browser.random_delay(1, 2)
                                    logger.info(f"✅ Подпись добавлена: {full_caption[:100]}...")
                                except Exception as e:
                                    logger.warning(f"Ошибка при добавлении подписи: {e}")
                            else:
                                logger.warning("⚠️ Не удалось найти поле для подписи")
                            
                            if not caption_added:
                                logger.warning("⚠️ Не удалось найти поле для подписи")
                                # Логируем все contenteditable элементы для отладки
                                try:
                                    all_editable = self.browser.page.query_selector_all('[contenteditable="true"]')
                                    logger.info(f"📊 Найдено contenteditable элементов: {len(all_editable)}")
                                    for i, elem in enumerate(all_editable[:10]):
                                        try:
                                            aria_label = elem.get_attribute('aria-label')
                                            aria_placeholder = elem.get_attribute('aria-placeholder')
                                            role = elem.get_attribute('role')
                                            is_visible = elem.is_visible()
                                            text_content = elem.text_content()[:50] if elem.text_content() else ''
                                            logger.info(f"📋 Элемент {i+1}: aria-label='{aria_label}', aria-placeholder='{aria_placeholder}', role='{role}', visible={is_visible}, text='{text_content}'")
                                        except:
                                            pass
                                    
                                    # Также ищем все элементы с role="textbox"
                                    all_textboxes = self.browser.page.query_selector_all('[role="textbox"]')
                                    logger.info(f"📊 Найдено элементов с role='textbox': {len(all_textboxes)}")
                                    for i, elem in enumerate(all_textboxes[:10]):
                                        try:
                                            aria_label = elem.get_attribute('aria-label')
                                            aria_placeholder = elem.get_attribute('aria-placeholder')
                                            is_visible = elem.is_visible()
                                            text_content = elem.text_content()[:50] if elem.text_content() else ''
                                            logger.info(f"📋 Textbox {i+1}: aria-label='{aria_label}', aria-placeholder='{aria_placeholder}', visible={is_visible}, text='{text_content}'")
                                        except:
                                            pass
                                    
                                    # Логируем текущий URL
                                    current_url = self.browser.page.url
                                    logger.info(f"📍 Текущий URL: {current_url}")
                                except Exception as debug_e:
                                    logger.debug(f"Ошибка при логировании: {debug_e}")
                except Exception as e:
                    logger.warning(f"Ошибка при добавлении подписи: {e}")
            
            # Проверяем связь аккаунтов и включаем чекбоксы
            accounts_linked = self._check_account_linking()
            
            if share_to_facebook and accounts_linked:
                logger.info("Включение кросспостинга в Facebook")
                facebook_checkbox_selectors = [
                    'input[type="checkbox"][aria-label*="Facebook"]',
                    'input[type="checkbox"][aria-label*="facebook"]',
                    '[aria-label*="Also share to Facebook"]',
                    '[aria-label*="Также делиться в Facebook"]',
                ]
                
                for selector in facebook_checkbox_selectors:
                    if self.browser.click(selector):
                        logger.info("Чекбокс 'Также делиться в Facebook' включен")
                        break
                
                self.browser.random_delay(1, 2)
            
            if add_to_story:
                logger.info("Включение опции 'Ваша история'")
                story_checkbox_selectors = [
                    'input[type="checkbox"][aria-label*="story"]',
                    'input[type="checkbox"][aria-label*="Story"]',
                    '[aria-label*="Your story"]',
                    '[aria-label*="Ваша история"]',
                ]
                
                for selector in story_checkbox_selectors:
                    if self.browser.click(selector):
                        logger.info("Опция 'Ваша история' включена")
                        break
                
                self.browser.random_delay(1, 2)
            
            # Шаг 7: Публикуем Reels
            logger.info("🚀 Публикация Reels...")
            publish_button_selectors = [
                'div[data-cursor-element-id]:has-text("Поделиться")',
                'div:has-text("Поделиться")',
                'div:has-text("Share")',
                'button:has-text("Поделиться")',
                'button:has-text("Share")',
                'text=/^Поделиться$/i',
                'text=/^Share$/i',
            ]
            
            published = False
            try:
                if hasattr(self.browser, 'page') and self.browser.page:
                    for selector in publish_button_selectors:
                        try:
                            publish_elem = self.browser.page.locator(selector).first
                            if publish_elem.is_visible(timeout=5000):
                                logger.info(f"✅ Найдена кнопка 'Поделиться': {selector}")
                                publish_elem.click(timeout=5000)
                                published = True
                                self.browser.random_delay(5, 8)  # Ждем публикации
                                break
                        except:
                            continue
            except Exception as e:
                logger.error(f"Ошибка при публикации: {e}")
            
            if not published:
                logger.warning("⚠️ Не удалось найти кнопку 'Поделиться', пробуем альтернативные селекторы...")
                publish_button_selectors_alt = [
                'button[type="submit"]:has-text("Share")',
                'button:has-text("Share")',
                'button[type="submit"]:has-text("Поделиться")',
                'button:has-text("Поделиться")',
                'div[role="button"]:has-text("Share")',
                'div[role="button"]:has-text("Поделиться")',
            ]
            
            published = False
            for selector in publish_button_selectors:
                if self.browser.click(selector):
                    published = True
                    break
            
            if not published:
                result['error'] = "Не удалось найти кнопку публикации"
                return result
            
            # Ждем завершения публикации
            logger.info("Ожидание завершения публикации...")
            self.browser.random_delay(5, 10)
            
            # Пытаемся получить ID поста из URL
            current_url = ""
            try:
                if hasattr(self.browser, 'page') and self.browser.page:
                    if hasattr(self.browser.page, 'url'):
                        current_url = self.browser.page.url
                elif hasattr(self.browser, 'driver') and self.browser.driver:
                    if hasattr(self.browser.driver, 'current_url'):
                        current_url = self.browser.driver.current_url
            except:
                pass
            
            if '/p/' in current_url or '/reel/' in current_url:
                # Извлекаем ID поста из URL
                post_id = current_url.split('/p/')[-1].split('/')[0] if '/p/' in current_url else current_url.split('/reel/')[-1].split('/')[0]
                result['instagram_post_id'] = post_id
                logger.info(f"Reels опубликован: {post_id}")
            
            result['success'] = True
            logger.info("Публикация Reels успешно завершена")
            
        except Exception as e:
            logger.error(f"Ошибка публикации Reels: {e}", exc_info=True)
            result['error'] = str(e)
        finally:
            # Удаляем временный файл
            if video_path and os.path.exists(video_path):
                try:
                    os.unlink(video_path)
                except:
                    pass
            
            # Закрываем браузер
            if self.browser:
                self.browser.close_browser()
        
        return result

