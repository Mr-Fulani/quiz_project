# Быстрое тестирование SEO компонентов

## 1. Тестирование robots.txt

```bash
# Через curl
curl https://quiz-code.com/robots.txt

# Через браузер
# Откройте: https://quiz-code.com/robots.txt
```

**Ожидаемый результат:**
- Статус: 200 OK
- Content-Type: text/plain
- Содержит: `Sitemap: https://quiz-code.com/sitemap.xml`

## 2. Тестирование sitemap.xml

```bash
# Через curl
curl https://quiz-code.com/sitemap.xml | head -50

# Проверка наличия hreflang
curl https://quiz-code.com/sitemap.xml | grep -c "hreflang"

# Проверка валидности XML
curl https://quiz-code.com/sitemap.xml | xmllint --noout -
```

**Ожидаемый результат:**
- Статус: 200 OK
- Content-Type: application/xml
- XML валиден
- Содержит hreflang теги для всех языков

## 3. Тестирование через Django команды

```bash
# Проверка robots.txt
docker compose exec quiz_backend python manage.py shell -c "
from django.test import Client
c = Client(HTTP_HOST='quiz-code.com')
r = c.get('/robots.txt')
print('Status:', r.status_code)
print('Content:', r.content.decode('utf-8')[:200])
"

# Проверка sitemap.xml
docker compose exec quiz_backend python manage.py shell -c "
from django.test import Client
c = Client(HTTP_HOST='quiz-code.com')
r = c.get('/sitemap.xml')
print('Status:', r.status_code)
print('Has hreflang:', 'hreflang' in r.content.decode('utf-8'))
"
```

## 4. Проверка HTML страниц

```bash
# Проверка canonical URL
curl https://quiz-code.com/en/ | grep -i canonical

# Проверка hreflang тегов
curl https://quiz-code.com/en/ | grep -i hreflang

# Проверка JSON-LD
curl https://quiz-code.com/en/ | grep -A 5 "application/ld+json"
```

## 5. Использование готового скрипта

```bash
# Запуск bash скрипта
./test_seo.sh https://quiz-code.com

# Запуск Python скрипта (требует настройки Django)
docker compose exec quiz_backend python test_seo_detailed.py
```

## Что проверить вручную

1. **robots.txt** - должен быть доступен и содержать правильный URL sitemap
2. **sitemap.xml** - должен быть валидным XML и содержать hreflang теги
3. **Canonical URLs** - должны использовать quiz-code.com, а не mini.quiz-code.com
4. **Hreflang теги** - должны присутствовать на всех страницах
5. **JSON-LD** - должен быть валидным JSON

## Онлайн инструменты для проверки

- **XML Sitemap Validator**: https://www.xml-sitemaps.com/validate-xml-sitemap.html
- **Google Search Console**: https://search.google.com/search-console
- **Schema.org Validator**: https://validator.schema.org/

