import re



def is_valid_url(url: str) -> bool:
    """
    Проверка корректности URL, поддерживает URL с и без схемы.
    """
    regex = re.compile(
        r'^(?:(?:http|ftp)s?://)?'  # Опциональная схема http://, https://, ftp:// или ftps://
        r'(?:\S+(?::\S*)?@)?'       # Опциональный пользователь и пароль
        r'(?:'
        r'(?P<ip>(?:\d{1,3}\.){3}\d{1,3})'  # IP адрес
        r'|'
        r'(?P<hostname>[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}'  # Доменное имя
        r')'
        r'(?::\d+)?'                 # Опциональный порт
        r'(?:/\S*)?$', re.IGNORECASE)
    return re.match(regex, url) is not None