"""
Браузерная автоматизация для публикации в социальные сети.
Поддерживает Playwright и Selenium для работы с платформами без API.
"""

from .base_browser import BaseBrowserAutomation
from .session_manager import BrowserSessionManager

__all__ = ['BaseBrowserAutomation', 'BrowserSessionManager']


