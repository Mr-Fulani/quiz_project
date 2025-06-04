from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _

class BreadcrumbsMixin:
    """
    Миксин для добавления хлебных крошек в контекст шаблона.

    Добавляет крошки в `context['breadcrumbs']` для использования в шаблонах или SEO.
    Поддерживает локализацию через gettext и структурированные данные schema.org/BreadcrumbList.
    Крошки задаются через атрибут `breadcrumbs` или метод `get_breadcrumbs`.
    По умолчанию добавляет крошку "Главная".
    """
    breadcrumbs = None

    def get_breadcrumbs(self):
        """
        Возвращает список хлебных крошек.

        Если атрибут `breadcrumbs` задан, возвращает его. Иначе возвращает базовую крошку "Главная".
        Можно переопределить в представлениях для динамических крошек.

        Returns:
            list: Список словарей [{'name': str, 'url': str}, ...]
        """
        if self.breadcrumbs:
            return self.breadcrumbs
        return [{'name': _('Главная'), 'url': reverse_lazy('blog:home')}]

    def get_context_data(self, **kwargs):
        """
        Добавляет хлебные крошки и структурированные данные JSON-LD в контекст.

        Args:
            **kwargs: Дополнительные аргументы для get_context_data.

        Returns:
            dict: Обновленный контекст с ключами 'breadcrumbs' и 'breadcrumbs_json_ld'.
        """
        context = super().get_context_data(**kwargs)
        breadcrumbs = self.get_breadcrumbs()
        context['breadcrumbs'] = breadcrumbs

        # Структурированные данные для SEO (schema.org/BreadcrumbList)
        breadcrumb_list = {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": index + 1,
                    "name": crumb['name'],
                    "item": self.request.build_absolute_uri(crumb['url']) if crumb['url'] else None
                }
                for index, crumb in enumerate(breadcrumbs) if crumb['url']
            ]
        }
        context['breadcrumbs_json_ld'] = breadcrumb_list
        return context