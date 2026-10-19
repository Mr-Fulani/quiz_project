"""
Сервис для работы со ссылками в кнопке 'Узнать больше о задаче'.
Логика приоритета:
1. external_link задачи (если указан админом)
2. DefaultLink для language + topic (специфичная для темы)
3. MainFallbackLink для language (главная для языка - ОБЯЗАТЕЛЬНА!)

ВАЖНО: Главные ссылки (MainFallbackLink) должны быть созданы для всех языков!
Если главной ссылки нет - задача не может быть опубликована.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class DefaultLinkService:
    """
    Сервис для работы со ссылками в кнопке 'Узнать больше о задаче'.
    Использует общие таблицы с ботом: default_links и main_fallback_links.
    
    Главная ссылка (MainFallbackLink) обязательна для каждого языка!
    """
    
    @staticmethod
    def _first_for_tenant(queryset, tenant):
        """Сначала запись тенанта, затем общая (tenant=None); записи других тенантов не берём."""
        if tenant is not None:
            own = queryset.filter(tenant=tenant).first()
            if own:
                return own
        return queryset.filter(tenant__isnull=True).first()

    @staticmethod
    def get_default_link(language: str, topic_name: str, tenant=None) -> Optional[str]:
        """
        Получает ссылку по умолчанию для языка и топика из общей таблицы с ботом.

        Args:
            language: Код языка (en, ru, ar, tr и т.д.)
            topic_name: Название топика
            tenant: Тенант задачи (ссылки других тенантов не используются)

        Returns:
            URL ссылки или None если не найдена
        """
        from webhooks.models import DefaultLink

        try:
            default_link = DefaultLinkService._first_for_tenant(
                DefaultLink.objects.filter(language=language.lower(), topic=topic_name), tenant
            )
            return default_link.link if default_link else None
        except Exception as e:
            logger.error(f"Ошибка получения DefaultLink для {language} + {topic_name}: {e}")
            return None

    @staticmethod
    def get_main_fallback_link(language: str, tenant=None) -> Optional[str]:
        """
        Получает главную ссылку для языка из общей таблицы с ботом.

        Args:
            language: Код языка (en, ru, ar, tr и т.д.)
            tenant: Тенант задачи (ссылки других тенантов не используются)

        Returns:
            URL ссылки или None если не найдена
        """
        from webhooks.models import MainFallbackLink

        try:
            main_link = DefaultLinkService._first_for_tenant(
                MainFallbackLink.objects.filter(language=language.lower()), tenant
            )
            return main_link.link if main_link else None
        except Exception as e:
            logger.error(f"Ошибка получения MainFallbackLink для {language}: {e}")
            return None
    
    @staticmethod
    def get_final_link(task, translation) -> tuple[Optional[str], str]:
        """
        Определяет итоговую ссылку для задачи по приоритету:
        1. external_link (если админ выбрал вручную)
        2. DefaultLink для language + topic (специфичная для темы)
        3. MainFallbackLink для language (главная для языка - ОБЯЗАТЕЛЬНА!)
        
        Args:
            task: Экземпляр Task
            translation: Экземпляр TaskTranslation или None
            
        Returns:
            Кортеж (url, source) где:
            - url: ссылка или None если нет главной ссылки для языка
            - source: описание источника ссылки
        """
        # Приоритет 1: external_link (админ выбрал вручную)
        if task.external_link:
            return task.external_link, "специфичная (выбрана вручную)"

        if translation:
            try:
                from django.conf import settings

                supported_languages = [
                    lang_code for lang_code, _ in getattr(settings, 'LANGUAGES', [('en', 'English'), ('ru', 'Russian')])
                ]

                requested_language = (translation.language or '').lower()
                effective_language = requested_language
                if effective_language not in supported_languages:
                    effective_language = getattr(settings, 'LANGUAGE_CODE', 'en').split('-')[0].lower() or 'en'
                    if effective_language not in supported_languages:
                        effective_language = 'en'

                if effective_language != requested_language:
                    logger.info(
                        "Язык '%s' не поддерживается сайтом, используем '%s' для генерации ссылки (task_id=%s)",
                        translation.language,
                        effective_language,
                        getattr(task, 'id', None),
                    )
            except Exception:
                requested_language = (translation.language or '').lower()
                effective_language = requested_language or 'en'

            # Приоритет 2: DefaultLink для language + topic
            if task.topic:
                default_link = DefaultLinkService.get_default_link(
                    effective_language,
                    task.topic.name,
                    tenant=task.tenant,
                )
                if default_link:
                    return default_link, f"для темы ({effective_language.upper()} + {task.topic.name})"

            # Приоритет 3: MainFallbackLink для language (ОБЯЗАТЕЛЬНА!)
            main_link = DefaultLinkService.get_main_fallback_link(effective_language, tenant=task.tenant)
            if main_link:
                return main_link, f"главная для языка ({effective_language.upper()})"
            else:
                # НЕТ главной ссылки для языка - это ошибка!
                logger.error(f"⚠️ Главная ссылка (MainFallbackLink) не найдена для языка {effective_language.upper()}!")
                return None, f"❌ НЕ НАЙДЕНА главная ссылка для языка ({effective_language.upper()})"
        
        # Нет перевода - не можем определить язык
        return None, "❌ Нет перевода для определения языка"
    
    @staticmethod
    def get_all_default_links(tenant=None) -> list[str]:
        """Получает уникальные URL из DefaultLink тенанта (и общих) для выпадающего списка"""
        from webhooks.models import DefaultLink
        from tenants.scoping import for_tenant_or_shared

        return list(
            for_tenant_or_shared(DefaultLink.objects.all(), tenant)
            .values_list('link', flat=True)
            .distinct()
            .order_by('link')
        )

