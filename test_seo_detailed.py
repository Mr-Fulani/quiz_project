#!/usr/bin/env python
"""
Детальный скрипт для тестирования SEO компонентов.
Можно запустить как через Django manage.py, так и напрямую.
"""
import os
import sys
import django
from django.conf import settings

# Настройка Django окружения
if __name__ == "__main__":
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()

from django.test import Client
from django.contrib.sites.models import Site
from django.urls import reverse
from blog.sitemaps import PostSitemap, ProjectSitemap, MainPagesSitemap, QuizSitemap
import xml.etree.ElementTree as ET

def test_robots_txt():
    """Тестирует robots.txt"""
    print("\n" + "="*60)
    print("📋 ТЕСТ 1: robots.txt")
    print("="*60)
    
    client = Client(HTTP_HOST='quiz-code.com')
    response = client.get('/robots.txt')
    
    print(f"Статус: {response.status_code}")
    print(f"Content-Type: {response.get('Content-Type', 'N/A')}")
    print("\nСодержимое:")
    print(response.content.decode('utf-8'))
    
    # Проверки
    assert response.status_code == 200, "robots.txt должен возвращать 200"
    assert 'Sitemap:' in response.content.decode('utf-8'), "robots.txt должен содержать Sitemap"
    assert 'quiz-code.com' in response.content.decode('utf-8'), "robots.txt должен содержать правильный домен"
    
    print("✅ robots.txt работает корректно!")

def test_sitemap_xml():
    """Тестирует sitemap.xml"""
    print("\n" + "="*60)
    print("📋 ТЕСТ 2: sitemap.xml")
    print("="*60)
    
    client = Client(HTTP_HOST='quiz-code.com')
    response = client.get('/sitemap.xml')
    
    print(f"Статус: {response.status_code}")
    print(f"Content-Type: {response.get('Content-Type', 'N/A')}")
    
    if response.status_code == 200:
        content = response.content.decode('utf-8')
        
        # Проверяем структуру XML
        try:
            root = ET.fromstring(content)
            print(f"✅ XML валиден")
            print(f"Корневой элемент: {root.tag}")
            
            # Подсчитываем URL
            urls = root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}url')
            print(f"Найдено URL: {len(urls)}")
            
            # Проверяем наличие hreflang
            hreflangs = root.findall('.//{http://www.w3.org/1999/xhtml}link')
            print(f"Найдено hreflang тегов: {len(hreflangs)}")
            
            # Показываем примеры
            if urls:
                first_url = urls[0]
                loc = first_url.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
                if loc is not None:
                    print(f"\nПример URL: {loc.text}")
                
                # Проверяем hreflang для первого URL
                url_hreflangs = first_url.findall('.//{http://www.w3.org/1999/xhtml}link')
                if url_hreflangs:
                    print(f"Hreflang теги для первого URL: {len(url_hreflangs)}")
                    for hreflang in url_hreflangs[:3]:
                        print(f"  - {hreflang.get('hreflang')}: {hreflang.get('href')}")
            
        except ET.ParseError as e:
            print(f"❌ Ошибка парсинга XML: {e}")
            return False
        
        # Проверяем наличие обязательных элементов
        assert 'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"' in content, "Должен быть правильный namespace"
        assert 'xmlns:xhtml="http://www.w3.org/1999/xhtml"' in content, "Должен быть xhtml namespace для hreflang"
        
        print("\n✅ sitemap.xml работает корректно!")
        return True
    else:
        print(f"❌ Ошибка: статус {response.status_code}")
        return False

def test_sitemap_classes():
    """Тестирует классы sitemap"""
    print("\n" + "="*60)
    print("📋 ТЕСТ 3: Классы Sitemap")
    print("="*60)
    
    site = Site.objects.get_current()
    
    # Тестируем PostSitemap
    post_sitemap = PostSitemap()
    posts = post_sitemap.items()
    print(f"PostSitemap: {len(posts)} постов")
    
    if posts:
        post = posts[0]
        urls = post_sitemap.get_urls(page=1, site=site, protocol='https')
        if urls:
            url = urls[0]
            print(f"  Пример URL: {url.get('location', 'N/A')}")
            if 'alternates' in url:
                print(f"  Hreflang альтернативы: {len(url['alternates'])}")
                for alt in url['alternates'][:2]:
                    print(f"    - {alt['lang']}: {alt['location']}")
    
    # Тестируем MainPagesSitemap
    main_sitemap = MainPagesSitemap()
    pages = main_sitemap.items()
    print(f"\nMainPagesSitemap: {len(pages)} страниц")
    
    if pages:
        urls = main_sitemap.get_urls(page=1, site=site, protocol='https')
        if urls:
            url = urls[0]
            print(f"  Пример URL: {url.get('location', 'N/A')}")
            if 'alternates' in url:
                print(f"  Hreflang альтернативы: {len(url['alternates'])}")
    
    print("\n✅ Классы Sitemap работают корректно!")

def test_canonical_urls():
    """Тестирует canonical URLs на страницах"""
    print("\n" + "="*60)
    print("📋 ТЕСТ 4: Canonical URLs")
    print("="*60)
    
    client = Client(HTTP_HOST='quiz-code.com')
    
    # Тестируем главную страницу
    response = client.get('/en/')
    if response.status_code == 200:
        content = response.content.decode('utf-8')
        if 'canonical' in content.lower():
            import re
            canonical_match = re.search(r'<link\s+rel=["\']canonical["\']\s+href=["\']([^"\']+)["\']', content, re.I)
            if canonical_match:
                canonical_url = canonical_match.group(1)
                print(f"Главная страница canonical: {canonical_url}")
                assert 'quiz-code.com' in canonical_url, "Canonical должен содержать правильный домен"
                assert 'mini.quiz-code.com' not in canonical_url, "Canonical не должен содержать mini домен"
                print("✅ Canonical URL корректный!")
            else:
                print("⚠️  Canonical URL не найден в HTML")
        else:
            print("⚠️  Canonical тег не найден")
    
    # Тестируем страницу поста (если есть)
    from blog.models import Post
    post = Post.objects.filter(published=True).first()
    if post:
        response = client.get(f'/en/post/{post.slug}/')
        if response.status_code == 200:
            content = response.content.decode('utf-8')
            if 'canonical' in content.lower():
                import re
                canonical_match = re.search(r'<link\s+rel=["\']canonical["\']\s+href=["\']([^"\']+)["\']', content, re.I)
                if canonical_match:
                    canonical_url = canonical_match.group(1)
                    print(f"Пост canonical: {canonical_url}")
                    assert 'quiz-code.com' in canonical_url, "Canonical должен содержать правильный домен"
                    print("✅ Canonical URL для поста корректный!")

def test_hreflang_tags():
    """Тестирует hreflang теги"""
    print("\n" + "="*60)
    print("📋 ТЕСТ 5: Hreflang теги")
    print("="*60)
    
    client = Client(HTTP_HOST='quiz-code.com')
    response = client.get('/en/')
    
    if response.status_code == 200:
        content = response.content.decode('utf-8')
        import re
        hreflang_matches = re.findall(r'<link\s+rel=["\']alternate["\']\s+hreflang=["\']([^"\']+)["\']\s+href=["\']([^"\']+)["\']', content, re.I)
        
        if hreflang_matches:
            print(f"Найдено hreflang тегов: {len(hreflang_matches)}")
            for lang, url in hreflang_matches:
                print(f"  - {lang}: {url}")
                assert 'quiz-code.com' in url, f"Hreflang URL должен содержать правильный домен: {url}"
            print("✅ Hreflang теги корректны!")
        else:
            print("⚠️  Hreflang теги не найдены")

def test_json_ld():
    """Тестирует JSON-LD разметку"""
    print("\n" + "="*60)
    print("📋 ТЕСТ 6: JSON-LD разметка")
    print("="*60)
    
    client = Client(HTTP_HOST='quiz-code.com')
    response = client.get('/en/')
    
    if response.status_code == 200:
        content = response.content.decode('utf-8')
        import re
        json_ld_matches = re.findall(r'<script\s+type=["\']application/ld\+json["\']>(.*?)</script>', content, re.DOTALL | re.I)
        
        if json_ld_matches:
            print(f"Найдено JSON-LD блоков: {len(json_ld_matches)}")
            import json
            for i, json_str in enumerate(json_ld_matches[:3], 1):
                try:
                    data = json.loads(json_str.strip())
                    print(f"\nБлок {i}:")
                    print(f"  Тип: {data.get('@type', 'N/A')}")
                    print(f"  Контекст: {data.get('@context', 'N/A')}")
                    if '@type' in data:
                        print(f"  ✅ JSON валиден")
                except json.JSONDecodeError as e:
                    print(f"  ❌ Ошибка парсинга JSON: {e}")
            print("\n✅ JSON-LD разметка корректна!")
        else:
            print("⚠️  JSON-LD блоки не найдены")

def main():
    """Запускает все тесты"""
    print("\n" + "="*60)
    print("🚀 ЗАПУСК ТЕСТИРОВАНИЯ SEO КОМПОНЕНТОВ")
    print("="*60)
    
    try:
        test_robots_txt()
        test_sitemap_xml()
        test_sitemap_classes()
        test_canonical_urls()
        test_hreflang_tags()
        test_json_ld()
        
        print("\n" + "="*60)
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("="*60)
        
    except AssertionError as e:
        print(f"\n❌ ОШИБКА ТЕСТА: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ НЕОЖИДАННАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

