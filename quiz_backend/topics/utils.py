from typing import Dict
import re


def normalize_subtopic_name(raw_name: str) -> str:
    """
    Приводит имя подтемы к каноническому виду.
    
    Используются простые правила: обрезка пробелов, замена спецсимволов и
    приведение регистра. Функция не предназначена для генерации slug'ов, только
    для унификации хранения в базе.
    """
    if not raw_name:
        return ''

    normalized = raw_name.strip()
    replacements: Dict[str, str] = {
        '&': ' and ',
        '+': ' plus ',
        '/': ' ',
    }
    for symbol, value in replacements.items():
        normalized = normalized.replace(symbol, value)

    normalized = normalized.lower()
    normalized = re.sub(r'\s+', ' ', normalized)
    normalized = normalized.title()
    return normalized

