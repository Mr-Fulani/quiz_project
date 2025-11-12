# Инструкция по тестированию SEO компонентов

## Быстрое тестирование

### 1. Тестирование через браузер

Откройте в браузере:
- `https://quiz-code.com/robots.txt` - должен показать содержимое robots.txt
- `https://quiz-code.com/sitemap.xml` - должен показать XML sitemap с hreflang тегами

### 2. Тестирование через curl

```bash
# Проверка robots.txt
curl -I https://quiz-code.com/robots.txt

# Проверка содержимого robots.txt
curl https://quiz-code.com/robots.txt

# Проверка sitemap.xml
curl -I https://quiz-code.com/sitemap.xml

# Проверка наличия hreflang в sitemap
curl https://quiz-code.com/sitemap.xml | grep -c "hreflang"

# Проверка валидности XML
curl https://quiz-code.com/sitemap.xml | xmllint --noout -
```

### 3. Тестирование через Django команды

```bash
# Запуск детального теста
docker compose exec quiz_backend python test_seo_detailed.py

# Или через manage.py shell
docker compose exec quiz_backend python manage.py shell < test_seo_detailed.py
```

### 4. Проверка HTML страниц

```bash
# Проверка canonical URL на главной странице
curl https://quiz-code.com/en/ | grep -i canonical

# Проверка hreflang тегов
curl https://quiz-code.com/en/ | grep -i hreflang

# Проверка JSON-LD разметки
curl https://quiz-code.com/en/ | grep -A 10 "application/ld+json"
```

## Детальное тестирование

### Использование скрипта test_seo.sh

```bash
# Тестирование на основном домене
./test_seo.sh https://quiz-code.com

# Тестирование на локальном сервере
./test_seo.sh http://localhost:8001
```

### Использование Python скрипта

```bash
# Запуск всех тестов
docker compose exec quiz_backend python test_seo_detailed.py
```

## Что проверять

### ✅ robots.txt
- [ ] Доступен по адресу `/robots.txt`
- [ ] Возвращает статус 200
- [ ] Содержит правильный домен в Sitemap
- [ ] Content-Type: text/plain

### ✅ sitemap.xml
- [ ] Доступен по адресу `/sitemap.xml`
- [ ] Возвращает статус 200
- [ ] Content-Type: application/xml
- [ ] XML валиден
- [ ] Содержит hreflang теги для всех языков
- [ ] Содержит правильные URL с доменом quiz-code.com

### ✅ Canonical URLs
- [ ] На всех страницах присутствует canonical тег
- [ ] Использует основной домен (quiz-code.com), а не mini.quiz-code.com
- [ ] URL корректный и полный

### ✅ Hreflang теги
- [ ] Присутствуют на всех страницах
- [ ] Содержат ссылки на все языковые версии
- [ ] Используют правильный домен
- [ ] Включен x-default

### ✅ JSON-LD разметка
- [ ] Присутствует на страницах
- [ ] JSON валиден
- [ ] Содержит правильные типы (WebSite, Organization, Article и т.д.)

## Проверка через Google Search Console

1. Откройте Google Search Console
2. Перейдите в раздел "Sitemaps"
3. Добавьте URL: `https://quiz-code.com/sitemap.xml`
4. Проверьте статус обработки

## Проверка через онлайн инструменты

- **XML Sitemap Validator**: https://www.xml-sitemaps.com/validate-xml-sitemap.html
- **Schema.org Validator**: https://validator.schema.org/
- **Google Rich Results Test**: https://search.google.com/test/rich-results
- **Facebook Sharing Debugger**: https://developers.facebook.com/tools/debug/

## Ожидаемые результаты

### robots.txt
```
User-agent: *
Disallow: /admin/
...
Sitemap: https://quiz-code.com/sitemap.xml
```

### sitemap.xml
Должен содержать структуру:
```xml
<urlset xmlns="..." xmlns:xhtml="...">
  <url>
    <loc>https://quiz-code.com/en/...</loc>
    <xhtml:link rel="alternate" hreflang="en" href="..." />
    <xhtml:link rel="alternate" hreflang="ru" href="..." />
  </url>
</urlset>
```

### HTML страницы
Должны содержать:
```html
<link rel="canonical" href="https://quiz-code.com/en/..." />
<link rel="alternate" hreflang="en" href="..." />
<link rel="alternate" hreflang="ru" href="..." />
<link rel="alternate" hreflang="x-default" href="..." />
```

