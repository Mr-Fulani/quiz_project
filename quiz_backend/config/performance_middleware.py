"""
Middleware для мониторинга производительности Django.

Отслеживает:
- Время обработки каждого запроса
- Количество SQL запросов
- Медленные запросы (> 1 секунды)
- Использование кэша
"""
import time
import logging
from django.conf import settings
from django.db import connection
from django.core.cache import cache

logger = logging.getLogger(__name__)


class PerformanceMonitoringMiddleware:
    """
    Middleware для мониторинга производительности запросов.
    
    Логирует:
    - Время выполнения запроса
    - Количество SQL запросов
    - Медленные запросы
    - URL и метод запроса
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.slow_request_threshold = 1.0  # 1 секунда
        self.sql_query_threshold = 20  # Больше 20 запросов = проблема

    def __call__(self, request):
        # Начало обработки запроса
        start_time = time.time()
        start_queries = len(connection.queries)
        
        # Обрабатываем запрос
        response = self.get_response(request)
        
        # Рассчитываем метрики
        total_time = time.time() - start_time
        total_queries = len(connection.queries) - start_queries
        
        # Логируем только в DEBUG или для медленных запросов
        if settings.DEBUG or total_time > self.slow_request_threshold:
            self._log_request_metrics(
                request=request,
                response=response,
                total_time=total_time,
                total_queries=total_queries,
            )
        
        # Добавляем метрики в заголовки ответа (только в DEBUG)
        if settings.DEBUG:
            response['X-Request-Time'] = f'{total_time:.3f}s'
            response['X-SQL-Queries'] = str(total_queries)
        
        return response

    def _log_request_metrics(self, request, response, total_time, total_queries):
        """Логирует метрики производительности запроса."""
        
        # Формируем базовое сообщение
        log_data = {
            'method': request.method,
            'path': request.path,
            'status': response.status_code,
            'time': f'{total_time:.3f}s',
            'queries': total_queries,
        }
        
        # Предупреждение о медленном запросе
        if total_time > self.slow_request_threshold:
            logger.warning(
                f"МЕДЛЕННЫЙ ЗАПРОС: {request.method} {request.path} "
                f"- {total_time:.3f}s, {total_queries} SQL запросов"
            )
        
        # Предупреждение о большом количестве SQL запросов
        if total_queries > self.sql_query_threshold:
            logger.warning(
                f"МНОГО SQL ЗАПРОСОВ: {request.method} {request.path} "
                f"- {total_queries} запросов за {total_time:.3f}s"
            )
        
        # Информационное логирование (только в DEBUG)
        if settings.DEBUG:
            logger.info(
                f"{request.method} {request.path} - "
                f"Status: {response.status_code}, "
                f"Time: {total_time:.3f}s, "
                f"Queries: {total_queries}"
            )


class CacheMetricsMiddleware:
    """
    Middleware для отслеживания использования кэша.
    
    Добавляет метрику попаданий/промахов кэша в заголовки ответа.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Сбрасываем счетчики
        cache_hits = 0
        cache_misses = 0
        
        # Обрабатываем запрос
        response = self.get_response(request)
        
        # В DEBUG режиме добавляем информацию о кэше
        if settings.DEBUG:
            try:
                # Для Redis можем получить реальную статистику
                if hasattr(cache, 'client') and hasattr(cache.client, 'get_client'):
                    redis_client = cache.client.get_client()
                    info = redis_client.info('stats')
                    
                    response['X-Cache-Hits'] = str(info.get('keyspace_hits', 0))
                    response['X-Cache-Misses'] = str(info.get('keyspace_misses', 0))
            except Exception as e:
                logger.debug(f"Не удалось получить метрики кэша: {str(e)}")
        
        return response


class DatabaseQueryLogger:
    """
    Middleware для детального логирования SQL запросов.
    
    Используется только в DEBUG режиме для анализа производительности.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Работает только в DEBUG
        if not settings.DEBUG:
            return self.get_response(request)
        
        # Запоминаем текущее количество запросов
        initial_queries = len(connection.queries)
        
        response = self.get_response(request)
        
        # Логируем новые запросы
        new_queries = connection.queries[initial_queries:]
        
        if new_queries:
            logger.debug(f"\n{'='*80}")
            logger.debug(f"SQL ЗАПРОСЫ для {request.method} {request.path}")
            logger.debug(f"{'='*80}")
            
            total_time = 0
            for idx, query in enumerate(new_queries, 1):
                sql = query['sql']
                exec_time = float(query['time'])
                total_time += exec_time
                
                # Помечаем медленные запросы
                slow_marker = " ⚠️  МЕДЛЕННЫЙ" if exec_time > 0.1 else ""
                
                logger.debug(f"\n{idx}. [{exec_time:.4f}s]{slow_marker}")
                logger.debug(f"   {sql}")
            
            logger.debug(f"\n{'='*80}")
            logger.debug(
                f"ИТОГО: {len(new_queries)} запросов за {total_time:.4f}s"
            )
            logger.debug(f"{'='*80}\n")
        
        return response


class RequestIDMiddleware:
    """
    Middleware для добавления уникального ID к каждому запросу.
    
    Помогает отслеживать запросы в логах.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        import uuid
        
        # Генерируем уникальный ID для запроса
        request_id = str(uuid.uuid4())[:8]
        request.request_id = request_id
        
        # Обрабатываем запрос
        response = self.get_response(request)
        
        # Добавляем ID в заголовки ответа
        response['X-Request-ID'] = request_id
        
        return response

