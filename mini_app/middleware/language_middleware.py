"""
Middleware для автоматического определения языка
"""
import logging
from typing import Optional
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from services.localization import localization_service

logger = logging.getLogger(__name__)

class LanguageMiddleware(BaseHTTPMiddleware):
    """Middleware для автоматического определения языка пользователя"""
    
    async def dispatch(self, request: Request, call_next):
        # Определяем язык из различных источников
        language = self._detect_language(request)
        
        # Устанавливаем язык в сервисе локализации
        localization_service.set_language(language)
        
        # Добавляем язык в request.state для использования в роутах
        request.state.language = language
        
        logger.debug(f"Language detected: {language} for {request.url.path}")
        
        response = await call_next(request)
        return response
    
    def _detect_language(self, request: Request) -> str:
        """Определяет язык из различных источников"""
        
        # 1. Из query параметра (приоритет 1)
        lang_param = request.query_params.get('lang')
        if lang_param and lang_param in localization_service.get_supported_languages():
            return lang_param
        
        # 2. Из заголовка Accept-Language (приоритет 2)
        accept_language = request.headers.get('accept-language', '')
        if accept_language:
            # Парсим Accept-Language заголовок
            for lang in accept_language.split(','):
                lang_code = lang.split(';')[0].strip().lower()
                if lang_code in localization_service.get_supported_languages():
                    return lang_code
                # Проверяем основную часть языка (например, 'en' из 'en-US')
                lang_base = lang_code.split('-')[0]
                if lang_base in localization_service.get_supported_languages():
                    return lang_base
        
        # 3. Из cookie (приоритет 3)
        lang_cookie = request.cookies.get('selected_language')
        if lang_cookie and lang_cookie in localization_service.get_supported_languages():
            return lang_cookie
        
        # 4. По умолчанию
        return localization_service.get_language() 