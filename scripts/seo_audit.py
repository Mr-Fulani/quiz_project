#!/usr/bin/env python3
"""SEO audit helper for quiz-code.com production.

Скрипт проверяет robots.txt, sitemap.xml и выборку HTML страниц
на наличие обязательных SEO-мета тегов.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from typing import Iterable, List, Tuple

import requests
from bs4 import BeautifulSoup
from requests import Response
from urllib.parse import urljoin
import xml.etree.ElementTree as ET

BASE_URL = "https://quiz-code.com"
SITEMAP_PATH = "/sitemap.xml"
ROBOTS_PATH = "/robots.txt"
DEFAULT_TIMEOUT = 15

EXPECTED_DISALLOWS = {
    "/admin/",
    "/api/",
    "/swagger/",
    "/redoc/",
    "/messages/",
    "/inbox/",
    "/silk/",
    "/__debug__/",
}
EXPECTED_ALLOW = "/"

EXPECTED_LANGS = {"en", "ru", "x-default"}

TEST_PAGES = [
    "/en/",
    "/ru/",
    "/en/post/krutoj-promt-dlya-gpt/",
    "/ru/post/krutoj-promt-dlya-gpt/",
]

@dataclass
class CheckResult:
    name: str
    ok: bool
    details: List[str]

    def add(self, message: str) -> None:
        self.details.append(message)

    @property
    def status_icon(self) -> str:
        return "✅" if self.ok else "❌"

    def format(self) -> str:
        header = f"{self.status_icon} {self.name}"
        if not self.details:
            return header
        body = "\n".join(f"   - {line}" for line in self.details)
        return f"{header}\n{body}"


def fetch(path: str) -> Response:
    url = urljoin(BASE_URL, path)
    resp = requests.get(url, timeout=DEFAULT_TIMEOUT)
    resp.raise_for_status()
    return resp


def check_robots() -> CheckResult:
    result = CheckResult("robots.txt", True, [])
    try:
        resp = fetch(ROBOTS_PATH)
    except Exception as exc:
        result.ok = False
        result.add(f"Ошибка запроса: {exc}")
        return result

    lines = [line.strip() for line in resp.text.splitlines() if line.strip()]
    disallows = {line.split(":", 1)[1].strip() for line in lines if line.lower().startswith("disallow:")}
    missing = EXPECTED_DISALLOWS - disallows
    if missing:
        result.ok = False
        result.add(f"Отсутствуют Disallow: {', '.join(sorted(missing))}")

    if EXPECTED_ALLOW not in {line.split(":", 1)[1].strip() for line in lines if line.lower().startswith("allow:")}:
        result.ok = False
        result.add("Отсутствует Allow: /")

    sitemap_lines = [line for line in lines if line.lower().startswith("sitemap:")]
    if not sitemap_lines:
        result.ok = False
        result.add("Не найдена строка Sitemap")

    return result


def check_sitemap() -> CheckResult:
    result = CheckResult("sitemap.xml", True, [])
    try:
        resp = fetch(SITEMAP_PATH)
    except Exception as exc:
        result.ok = False
        result.add(f"Ошибка запроса: {exc}")
        return result

    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError as exc:
        result.ok = False
        result.add(f"Ошибка парсинга XML: {exc}")
        return result

    ns = {
        "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
        "xhtml": "http://www.w3.org/1999/xhtml",
        "image": "http://www.google.com/schemas/sitemap-image/1.1",
    }

    urls = root.findall("sm:url", ns)
    if not urls:
        result.ok = False
        result.add("Не найдены элементы <url>")
        return result

    missing_langs: set[str] = set()
    http_links: List[str] = []

    for url_el in urls:
        loc_el = url_el.find("sm:loc", ns)
        if loc_el is None:
            continue
        loc_text = loc_el.text or ""
        if loc_text.startswith("http://"):
            http_links.append(loc_text)

        alternates = url_el.findall("xhtml:link", ns)
        langs = {alt.get("hreflang") for alt in alternates if alt.get("hreflang")}
        missing_for_url = EXPECTED_LANGS - langs
        if missing_for_url:
            missing_langs.update(missing_for_url)

    if http_links:
        result.ok = False
        result.add("Найдены ссылки http: " + ", ".join(http_links[:5]))
        if len(http_links) > 5:
            result.add(f"... и ещё {len(http_links) - 5} ссылок")

    if missing_langs:
        result.ok = False
        result.add("Не для всех URL есть hreflang: " + ", ".join(sorted(missing_langs)))

    result.add(f"Всего URL: {len(urls)}")
    return result


def check_page(path: str) -> CheckResult:
    result = CheckResult(f"Страница {path}", True, [])
    try:
        resp = fetch(path)
    except Exception as exc:
        result.ok = False
        result.add(f"Ошибка запроса: {exc}")
        return result

    soup = BeautifulSoup(resp.text, "html.parser")

    canonical = soup.find("link", rel="canonical")
    if not canonical or not canonical.get("href"):
        result.ok = False
        result.add("Отсутствует canonical")
    elif canonical["href"].startswith("http://"):
        result.ok = False
        result.add(f"Canonical указывает на http: {canonical['href']}")

    hreflangs = soup.find_all("link", rel="alternate")
    langs = {link.get("hreflang") for link in hreflangs if link.get("hreflang")}
    missing = EXPECTED_LANGS - langs
    if missing:
        result.ok = False
        result.add("Нет hreflang: " + ", ".join(sorted(missing)))

    ga_loaded = any(
        'www.googletagmanager.com/gtag/js' in script.get("src", "")
        for script in soup.find_all("script")
    )
    if not ga_loaded:
        result.ok = False
        result.add("Google Analytics не найден на странице")

    return result


def run_checks(pages: Iterable[str]) -> List[CheckResult]:
    results = [check_robots(), check_sitemap()]
    results.extend(check_page(path) for path in pages)
    return results


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SEO audit utility for quiz-code.com")
    parser.add_argument(
        "--pages",
        nargs="*",
        default=TEST_PAGES,
        help="Дополнительные страницы для проверки",
    )
    args = parser.parse_args(argv)

    results = run_checks(args.pages)
    for res in results:
        print(res.format())
        print()

    if all(res.ok for res in results):
        print("Итог: ✅ все проверки пройдены")
        return 0
    print("Итог: ❌ есть замечания")
    return 1


if __name__ == "__main__":
    sys.exit(main())
