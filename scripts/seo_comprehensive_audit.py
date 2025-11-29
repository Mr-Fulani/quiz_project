#!/usr/bin/env python3
"""
Комплексный SEO-аудит сайта quiz-code.com

Скрипт проверяет:
- Редиректы (301, 302, 307, 308) и цепочки редиректов
- Доступность всех URL из sitemap.xml
- Правильность canonical URLs
- Hreflang теги
- robots.txt
- Мета-теги (robots, canonical)
- HTTP статусы
- Генерирует детальный отчет с рекомендациями
"""
from __future__ import annotations

import argparse
import sys
import json
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin, urlparse
from datetime import datetime
import re

import requests
from bs4 import BeautifulSoup
from requests import Response
import xml.etree.ElementTree as ET

BASE_URL = "https://quiz-code.com"
SITEMAP_PATH = "/sitemap.xml"
ROBOTS_PATH = "/robots.txt"
DEFAULT_TIMEOUT = 15
MAX_REDIRECT_CHAIN = 5  # Максимальная длина цепочки редиректов для анализа
MAX_URLS_PER_CATEGORY = 10  # Максимальное количество URL из каждой категории для проверки

EXPECTED_LANGS = {"en", "ru", "x-default"}


@dataclass
class RedirectInfo:
    """Информация о редиректе"""
    url: str
    status_code: int
    location: Optional[str] = None
    is_permanent: bool = False
    redirect_type: str = ""  # "301", "302", "307", "308"


@dataclass
class RedirectChain:
    """Цепочка редиректов"""
    start_url: str
    final_url: str
    chain: List[RedirectInfo]
    is_too_long: bool = False
    has_302: bool = False


@dataclass
class PageCheckResult:
    """Результат проверки страницы"""
    url: str
    status_code: int
    has_canonical: bool = False
    canonical_url: Optional[str] = None
    canonical_issues: List[str] = None
    hreflang_tags: Dict[str, str] = None  # lang -> url
    missing_hreflang: List[str] = None
    has_robots_meta: bool = False
    robots_content: Optional[str] = None
    redirect_chain: Optional[RedirectChain] = None
    errors: List[str] = None

    def __post_init__(self):
        if self.canonical_issues is None:
            self.canonical_issues = []
        if self.hreflang_tags is None:
            self.hreflang_tags = {}
        if self.missing_hreflang is None:
            self.missing_hreflang = []
        if self.errors is None:
            self.errors = []


@dataclass
class AuditResult:
    """Общий результат аудита"""
    timestamp: str
    base_url: str
    robots_check: Dict
    sitemap_check: Dict
    redirect_issues: List[RedirectChain]
    pages_check: List[PageCheckResult]
    summary: Dict
    recommendations: List[str]


class SEOAuditor:
    """Класс для выполнения SEO-аудита"""

    def __init__(self, base_url: str = BASE_URL, timeout: int = DEFAULT_TIMEOUT):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; SEO-Audit-Bot/1.0)'
        })

    def fetch_with_redirects(self, path: str, follow: bool = True) -> Tuple[Response, Optional[RedirectChain]]:
        """
        Получает URL с отслеживанием редиректов
        
        Returns:
            Tuple[Response, Optional[RedirectChain]]: Ответ и цепочка редиректов
        """
        url = urljoin(self.base_url, path)
        redirect_chain = None
        
        if not follow:
            # Отслеживаем редиректы вручную
            redirect_chain = RedirectChain(
                start_url=url,
                final_url=url,
                chain=[]
            )
            
            current_url = url
            visited_urls = set()
            
            for _ in range(MAX_REDIRECT_CHAIN):
                if current_url in visited_urls:
                    break
                visited_urls.add(current_url)
                
                try:
                    resp = self.session.get(
                        current_url,
                        timeout=self.timeout,
                        allow_redirects=False
                    )
                except Exception as e:
                    return resp if 'resp' in locals() else None, redirect_chain
                
                redirect_chain.final_url = current_url
                
                # Проверяем, является ли ответ редиректом
                if resp.status_code in [301, 302, 307, 308]:
                    redirect_info = RedirectInfo(
                        url=current_url,
                        status_code=resp.status_code,
                        location=resp.headers.get('Location'),
                        is_permanent=resp.status_code in [301, 308],
                        redirect_type=str(resp.status_code)
                    )
                    redirect_chain.chain.append(redirect_info)
                    
                    if redirect_info.status_code == 302:
                        redirect_chain.has_302 = True
                    
                    # Переходим к следующему URL
                    location = redirect_info.location
                    if not location:
                        break
                    
                    # Обрабатываем относительные URL
                    if location.startswith('/'):
                        parsed = urlparse(current_url)
                        location = f"{parsed.scheme}://{parsed.netloc}{location}"
                    elif not location.startswith('http'):
                        location = urljoin(current_url, location)
                    
                    current_url = location
                else:
                    # Не редирект - возвращаем ответ
                    redirect_chain.final_url = current_url
                    return resp, redirect_chain
            
            # Цепочка слишком длинная
            redirect_chain.is_too_long = len(redirect_chain.chain) >= MAX_REDIRECT_CHAIN
            # Последний запрос для получения финального ответа
            try:
                resp = self.session.get(current_url, timeout=self.timeout, allow_redirects=True)
            except Exception as e:
                resp = Response()
                resp.status_code = 0
            return resp, redirect_chain
        else:
            try:
                resp = self.session.get(url, timeout=self.timeout, allow_redirects=True)
                return resp, None
            except Exception as e:
                resp = Response()
                resp.status_code = 0
                return resp, None

    def check_robots(self) -> Dict:
        """Проверяет robots.txt"""
        result = {
            'ok': True,
            'status_code': None,
            'errors': [],
            'content': None,
            'has_sitemap': False,
            'sitemap_url': None
        }
        
        try:
            resp, _ = self.fetch_with_redirects(ROBOTS_PATH, follow=True)
            result['status_code'] = resp.status_code
            
            if resp.status_code != 200:
                result['ok'] = False
                result['errors'].append(f"robots.txt возвращает статус {resp.status_code}")
                return result
            
            result['content'] = resp.text
            lines = [line.strip() for line in resp.text.splitlines() if line.strip()]
            
            # Проверяем наличие sitemap
            sitemap_lines = [line for line in lines if line.lower().startswith("sitemap:")]
            if sitemap_lines:
                result['has_sitemap'] = True
                result['sitemap_url'] = sitemap_lines[0].split(":", 1)[1].strip()
            else:
                result['ok'] = False
                result['errors'].append("Не найдена строка Sitemap в robots.txt")
        
        except Exception as e:
            result['ok'] = False
            result['errors'].append(f"Ошибка при проверке robots.txt: {e}")
        
        return result

    def get_sitemap_urls(self) -> List[str]:
        """Извлекает все URL из sitemap.xml"""
        urls = []
        
        try:
            resp, _ = self.fetch_with_redirects(SITEMAP_PATH, follow=True)
            if resp.status_code != 200:
                return urls
            
            root = ET.fromstring(resp.text)
            ns = {
                "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
                "xhtml": "http://www.w3.org/1999/xhtml",
            }
            
            url_elements = root.findall("sm:url", ns)
            for url_el in url_elements:
                loc_el = url_el.find("sm:loc", ns)
                if loc_el is not None and loc_el.text:
                    urls.append(loc_el.text)
        
        except Exception as e:
            print(f"Ошибка при парсинге sitemap: {e}", file=sys.stderr)
        
        return urls

    def check_sitemap(self) -> Dict:
        """Проверяет sitemap.xml"""
        result = {
            'ok': True,
            'status_code': None,
            'errors': [],
            'url_count': 0,
            'has_http_links': False,
            'http_links': [],
            'missing_hreflang': set()
        }
        
        try:
            resp, _ = self.fetch_with_redirects(SITEMAP_PATH, follow=True)
            result['status_code'] = resp.status_code
            
            if resp.status_code != 200:
                result['ok'] = False
                result['errors'].append(f"sitemap.xml возвращает статус {resp.status_code}")
                return result
            
            root = ET.fromstring(resp.text)
            ns = {
                "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
                "xhtml": "http://www.w3.org/1999/xhtml",
            }
            
            url_elements = root.findall("sm:url", ns)
            result['url_count'] = len(url_elements)
            
            for url_el in url_elements:
                loc_el = url_el.find("sm:loc", ns)
                if loc_el is None:
                    continue
                
                loc_text = loc_el.text or ""
                
                # Проверяем на http:// ссылки
                if loc_text.startswith("http://"):
                    result['has_http_links'] = True
                    result['http_links'].append(loc_text)
                
                # Проверяем hreflang
                alternates = url_el.findall("xhtml:link", ns)
                langs = {alt.get("hreflang") for alt in alternates if alt.get("hreflang")}
                missing = EXPECTED_LANGS - langs
                if missing:
                    result['missing_hreflang'].update(missing)
            
            result['missing_hreflang'] = list(result['missing_hreflang'])
            
            if result['has_http_links']:
                result['ok'] = False
                result['errors'].append(f"Найдены http:// ссылки в sitemap ({len(result['http_links'])} шт.)")
            
            if result['missing_hreflang']:
                result['ok'] = False
                result['errors'].append(f"Не для всех URL есть hreflang теги: {', '.join(sorted(result['missing_hreflang']))}")
        
        except Exception as e:
            result['ok'] = False
            result['errors'].append(f"Ошибка при проверке sitemap.xml: {e}")
        
        return result

    def check_page(self, url: str, check_redirects: bool = True) -> PageCheckResult:
        """
        Проверяет отдельную страницу
        
        Args:
            url: Полный URL или путь
            check_redirects: Проверять ли редиректы
        """
        # Если URL относительный, делаем его полным
        if not url.startswith('http'):
            url = urljoin(self.base_url, url)
        
        result = PageCheckResult(url=url, status_code=0)
        
        try:
            if check_redirects:
                resp, redirect_chain = self.fetch_with_redirects(url, follow=False)
            else:
                resp, redirect_chain = self.fetch_with_redirects(url, follow=True)
            
            result.status_code = resp.status_code
            
            if redirect_chain and redirect_chain.chain:
                result.redirect_chain = redirect_chain
            
            if resp.status_code != 200:
                result.errors.append(f"Статус код: {resp.status_code}")
                return result
            
            # Парсим HTML
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # Проверяем canonical
            canonical = soup.find("link", rel="canonical")
            if canonical and canonical.get("href"):
                result.has_canonical = True
                result.canonical_url = canonical["href"]
                
                # Проверки canonical URL
                if result.canonical_url.startswith("http://"):
                    result.canonical_issues.append("Canonical использует http:// вместо https://")
                
                parsed_canonical = urlparse(result.canonical_url)
                parsed_current = urlparse(url)
                
                # Проверяем, что canonical использует основной домен
                if 'mini.' in parsed_canonical.netloc:
                    result.canonical_issues.append(f"Canonical использует mini домен: {parsed_canonical.netloc}")
                
                # Проверяем, что canonical указывает на правильный URL (без лишних параметров)
                canonical_path = parsed_canonical.path
                current_path = parsed_current.path
                if canonical_path != current_path:
                    # Это не обязательно ошибка, но стоит проверить
                    pass
            
            # Проверяем hreflang
            hreflang_links = soup.find_all("link", rel="alternate", hreflang=True)
            for link in hreflang_links:
                lang = link.get("hreflang")
                href = link.get("href")
                if lang and href:
                    result.hreflang_tags[lang] = href
            
            # Проверяем недостающие языки
            found_langs = set(result.hreflang_tags.keys())
            result.missing_hreflang = list(EXPECTED_LANGS - found_langs)
            
            # Проверяем robots meta тег
            robots_meta = soup.find("meta", attrs={"name": "robots"})
            if robots_meta:
                result.has_robots_meta = True
                result.robots_content = robots_meta.get("content", "")
        
        except Exception as e:
            result.errors.append(f"Ошибка при проверке страницы: {e}")
        
        return result

    def check_redirects_for_key_urls(self) -> List[RedirectChain]:
        """Проверяет редиректы для ключевых URL"""
        key_urls = [
            '/',  # Корневой URL
            '/post/test-slug/',  # Пост без языкового префикса (если есть такой)
        ]
        
        issues = []
        
        for path in key_urls:
            url = urljoin(self.base_url, path)
            resp, redirect_chain = self.fetch_with_redirects(path, follow=False)
            
            if redirect_chain and redirect_chain.chain:
                # Проверяем, есть ли проблемы
                if redirect_chain.has_302:
                    issues.append(redirect_chain)
                if redirect_chain.is_too_long:
                    issues.append(redirect_chain)
                if len(redirect_chain.chain) > 2:  # Цепочка более 2 редиректов
                    issues.append(redirect_chain)
        
        return issues

    def run_audit(self, max_urls: int = MAX_URLS_PER_CATEGORY) -> AuditResult:
        """Запускает полный аудит"""
        print("🔍 Запуск комплексного SEO-аудита...")
        print(f"📍 Базовый URL: {self.base_url}\n")
        
        # Проверка robots.txt
        print("📋 Проверка robots.txt...")
        robots_check = self.check_robots()
        if robots_check['ok']:
            print("   ✅ robots.txt в порядке")
        else:
            print(f"   ❌ Проблемы: {', '.join(robots_check['errors'])}")
        
        # Проверка sitemap.xml
        print("\n📋 Проверка sitemap.xml...")
        sitemap_check = self.check_sitemap()
        print(f"   Найдено URL в sitemap: {sitemap_check['url_count']}")
        if sitemap_check['ok']:
            print("   ✅ sitemap.xml в порядке")
        else:
            print(f"   ❌ Проблемы: {', '.join(sitemap_check['errors'])}")
        
        # Проверка редиректов для ключевых URL
        print("\n🔄 Проверка редиректов для ключевых URL...")
        redirect_issues = self.check_redirects_for_key_urls()
        if redirect_issues:
            print(f"   ⚠️  Найдено проблемных редиректов: {len(redirect_issues)}")
            for issue in redirect_issues:
                if issue.has_302:
                    print(f"      - {issue.start_url}: найдены 302 редиректы (должны быть 301)")
                if issue.is_too_long:
                    print(f"      - {issue.start_url}: цепочка редиректов слишком длинная ({len(issue.chain)} редиректов)")
        else:
            print("   ✅ Редиректы в порядке")
        
        # Проверка URL из sitemap
        print(f"\n📄 Проверка до {max_urls} URL из каждой категории sitemap...")
        sitemap_urls = self.get_sitemap_urls()
        
        # Группируем URL по категориям
        url_categories: Dict[str, List[str]] = {}
        for url in sitemap_urls:
            # Определяем категорию по пути
            parsed = urlparse(url)
            path = parsed.path
            
            if '/post/' in path:
                category = 'posts'
            elif '/project/' in path:
                category = 'projects'
            elif path in ['/en/', '/ru/', '/']:
                category = 'main_pages'
            elif '/quiz' in path or '/quizes' in path:
                category = 'quizzes'
            else:
                category = 'other'
            
            if category not in url_categories:
                url_categories[category] = []
            url_categories[category].append(url)
        
        pages_check = []
        for category, urls in url_categories.items():
            print(f"   Проверка {category} ({min(len(urls), max_urls)} URL)...")
            for url in urls[:max_urls]:
                # Извлекаем путь относительно базового URL
                parsed = urlparse(url)
                path = parsed.path
                
                page_result = self.check_page(path, check_redirects=True)
                pages_check.append(page_result)
                
                # Выводим прогресс для проблемных страниц
                if page_result.errors or page_result.canonical_issues or page_result.missing_hreflang:
                    print(f"      ⚠️  {path}: проблемы обнаружены")
        
        # Формируем статистику
        print("\n📊 Анализ результатов...")
        status_codes = {}
        redirect_count = 0
        canonical_issues_count = 0
        hreflang_issues_count = 0
        
        for page in pages_check:
            status_codes[page.status_code] = status_codes.get(page.status_code, 0) + 1
            if page.redirect_chain and page.redirect_chain.chain:
                redirect_count += 1
            if page.canonical_issues:
                canonical_issues_count += 1
            if page.missing_hreflang:
                hreflang_issues_count += 1
        
        summary = {
            'total_pages_checked': len(pages_check),
            'status_codes': status_codes,
            'pages_with_redirects': redirect_count,
            'pages_with_canonical_issues': canonical_issues_count,
            'pages_with_hreflang_issues': hreflang_issues_count,
        }
        
        # Генерируем рекомендации
        recommendations = []
        
        if redirect_issues:
            recommendations.append(
                "Исправить 302 редиректы на 301 для SEO-критичных URL "
                "(корневой URL, посты без языкового префикса)"
            )
        
        if canonical_issues_count > 0:
            recommendations.append(
                f"Исправить canonical URL на {canonical_issues_count} страницах "
                "(использовать https:// и основной домен)"
            )
        
        if hreflang_issues_count > 0:
            recommendations.append(
                f"Добавить недостающие hreflang теги на {hreflang_issues_count} страницах"
            )
        
        if sitemap_check.get('has_http_links'):
            recommendations.append(
                "Заменить все http:// ссылки на https:// в sitemap.xml"
            )
        
        if not recommendations:
            recommendations.append("Все проверки пройдены успешно! ✅")
        
        result = AuditResult(
            timestamp=datetime.now().isoformat(),
            base_url=self.base_url,
            robots_check=robots_check,
            sitemap_check=sitemap_check,
            redirect_issues=redirect_issues,
            pages_check=pages_check,
            summary=summary,
            recommendations=recommendations
        )
        
        return result


def format_report(result: AuditResult) -> str:
    """Форматирует отчет в читаемый вид"""
    lines = []
    lines.append("=" * 80)
    lines.append("SEO АУДИТ ОТЧЕТ")
    lines.append("=" * 80)
    lines.append(f"Дата: {result.timestamp}")
    lines.append(f"Базовый URL: {result.base_url}")
    lines.append("")
    
    # Robots.txt
    lines.append("ROBOTS.TXT")
    lines.append("-" * 80)
    if result.robots_check['ok']:
        lines.append("✅ robots.txt работает корректно")
    else:
        lines.append("❌ Проблемы с robots.txt:")
        for error in result.robots_check['errors']:
            lines.append(f"   - {error}")
    lines.append("")
    
    # Sitemap
    lines.append("SITEMAP.XML")
    lines.append("-" * 80)
    lines.append(f"Всего URL в sitemap: {result.sitemap_check['url_count']}")
    if result.sitemap_check['ok']:
        lines.append("✅ sitemap.xml работает корректно")
    else:
        lines.append("❌ Проблемы с sitemap.xml:")
        for error in result.sitemap_check['errors']:
            lines.append(f"   - {error}")
    lines.append("")
    
    # Редиректы
    lines.append("РЕДИРЕКТЫ")
    lines.append("-" * 80)
    if result.redirect_issues:
        lines.append(f"⚠️  Найдено проблемных редиректов: {len(result.redirect_issues)}")
        for issue in result.redirect_issues:
            lines.append(f"\n   URL: {issue.start_url}")
            lines.append(f"   Финальный URL: {issue.final_url}")
            lines.append(f"   Цепочка редиректов ({len(issue.chain)}):")
            for i, redirect in enumerate(issue.chain, 1):
                lines.append(f"      {i}. {redirect.status_code} → {redirect.location}")
            if issue.has_302:
                lines.append("   ⚠️  В цепочке есть 302 редиректы (должны быть 301)")
            if issue.is_too_long:
                lines.append("   ⚠️  Цепочка редиректов слишком длинная")
    else:
        lines.append("✅ Проблемных редиректов не найдено")
    lines.append("")
    
    # Статистика страниц
    lines.append("СТАТИСТИКА ПРОВЕРЕННЫХ СТРАНИЦ")
    lines.append("-" * 80)
    lines.append(f"Всего проверено: {result.summary['total_pages_checked']}")
    lines.append(f"С редиректами: {result.summary['pages_with_redirects']}")
    lines.append(f"С проблемами canonical: {result.summary['pages_with_canonical_issues']}")
    lines.append(f"С проблемами hreflang: {result.summary['pages_with_hreflang_issues']}")
    lines.append("\nСтатус коды:")
    for status, count in sorted(result.summary['status_codes'].items()):
        lines.append(f"   {status}: {count}")
    lines.append("")
    
    # Проблемные страницы
    problematic_pages = [
        p for p in result.pages_check
        if p.errors or p.canonical_issues or p.missing_hreflang or (p.redirect_chain and p.redirect_chain.has_302)
    ]
    
    if problematic_pages:
        lines.append("ПРОБЛЕМНЫЕ СТРАНИЦЫ")
        lines.append("-" * 80)
        for page in problematic_pages[:20]:  # Показываем первые 20
            lines.append(f"\n   {page.url}")
            if page.errors:
                for error in page.errors:
                    lines.append(f"      ❌ {error}")
            if page.canonical_issues:
                for issue in page.canonical_issues:
                    lines.append(f"      ⚠️  Canonical: {issue}")
            if page.missing_hreflang:
                lines.append(f"      ⚠️  Отсутствуют hreflang: {', '.join(page.missing_hreflang)}")
            if page.redirect_chain and page.redirect_chain.has_302:
                lines.append(f"      ⚠️  Найдены 302 редиректы в цепочке")
        if len(problematic_pages) > 20:
            lines.append(f"\n   ... и ещё {len(problematic_pages) - 20} страниц с проблемами")
    lines.append("")
    
    # Рекомендации
    lines.append("РЕКОМЕНДАЦИИ")
    lines.append("-" * 80)
    for i, rec in enumerate(result.recommendations, 1):
        lines.append(f"{i}. {rec}")
    lines.append("")
    
    lines.append("=" * 80)
    
    return "\n".join(lines)


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Комплексный SEO-аудит для quiz-code.com"
    )
    parser.add_argument(
        "--base-url",
        default=BASE_URL,
        help=f"Базовый URL сайта (по умолчанию: {BASE_URL})"
    )
    parser.add_argument(
        "--max-urls",
        type=int,
        default=MAX_URLS_PER_CATEGORY,
        help=f"Максимальное количество URL из каждой категории для проверки (по умолчанию: {MAX_URLS_PER_CATEGORY})"
    )
    parser.add_argument(
        "--output",
        help="Путь к файлу для сохранения отчета (JSON)"
    )
    parser.add_argument(
        "--report",
        help="Путь к файлу для сохранения текстового отчета"
    )
    
    args = parser.parse_args(argv)
    
    auditor = SEOAuditor(base_url=args.base_url)
    result = auditor.run_audit(max_urls=args.max_urls)
    
    # Выводим краткий отчет в консоль
    print("\n" + "=" * 80)
    print("КРАТКИЙ ОТЧЕТ")
    print("=" * 80)
    print(format_report(result))
    
    # Сохраняем JSON отчет
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            # Преобразуем dataclass в dict для сериализации
            result_dict = {
                'timestamp': result.timestamp,
                'base_url': result.base_url,
                'robots_check': result.robots_check,
                'sitemap_check': result.sitemap_check,
                'redirect_issues': [
                    {
                        'start_url': issue.start_url,
                        'final_url': issue.final_url,
                        'chain': [asdict(r) for r in issue.chain],
                        'is_too_long': issue.is_too_long,
                        'has_302': issue.has_302,
                    }
                    for issue in result.redirect_issues
                ],
                'pages_check': [
                    {
                        'url': page.url,
                        'status_code': page.status_code,
                        'has_canonical': page.has_canonical,
                        'canonical_url': page.canonical_url,
                        'canonical_issues': page.canonical_issues,
                        'hreflang_tags': page.hreflang_tags,
                        'missing_hreflang': page.missing_hreflang,
                        'has_robots_meta': page.has_robots_meta,
                        'robots_content': page.robots_content,
                        'errors': page.errors,
                    }
                    for page in result.pages_check
                ],
                'summary': result.summary,
                'recommendations': result.recommendations,
            }
            json.dump(result_dict, f, ensure_ascii=False, indent=2)
        print(f"\n✅ JSON отчет сохранен в {args.output}")
    
    # Сохраняем текстовый отчет
    if args.report:
        with open(args.report, 'w', encoding='utf-8') as f:
            f.write(format_report(result))
        print(f"✅ Текстовый отчет сохранен в {args.report}")
    
    # Возвращаем код выхода
    if result.recommendations and not all("✅" in rec for rec in result.recommendations):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

