# bot/utils/url_validator.py

import re



def is_valid_url(url: str) -> bool:
    """
    Простая проверка корректности URL.
    """
    regex = re.compile(
        r'^(?:http|ftp)s?://'  # http:// или https://
        r'(?:\S+(?::\S*)?@)?'  # пользователь и пароль
        r'(?:'
        r'(?P<ip>(?:\d{1,3}\.){3}\d{1,3})'  # IP адрес
        r'|'
        r'(?P<hostname>[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}'  # Доменное имя
        r')'
        r'(?::\d+)?'  # порт
        r'(?:/\S*)?$', re.IGNORECASE)
    return re.match(regex, url) is not None