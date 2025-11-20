import re



def escape_markdown(text: str) -> str:
    """
    Экранирование специальных символов для MarkdownV2
    """
    if text is None:
        return ""

    text = str(text)

    # Список символов для экранирования
    markdown_escape_chars = r'_*[]()~`>#+-=|{}.!'

    # Экранируем каждый специальный символ
    result = ""
    for char in text:
        if char in markdown_escape_chars:
            result += f'\\{char}'
        else:
            result += char

    return result



def escape_markdown_except_urls(text: str) -> str:
    """
    Экранирование специальных символов в тексте, но игнорирование URL внутри ссылок MarkdownV2
    """
    if text is None:
        return ""

    # Регулярное выражение для поиска markdown-ссылок: [текст](url)
    pattern = r'(\[.*?\]\()(.*?)(\))'

    parts = []
    last_end = 0

    for match in re.finditer(pattern, text):
        # Обрабатываем текст перед ссылкой
        start, end = match.span()
        if start > last_end:
            parts.append(escape_markdown(text[last_end:start]))

        # Разбиваем ссылку на части
        link_text_part = match.group(1)  # [текст](
        url_part = match.group(2)  # url
        closing_part = match.group(3)  # )

        # Экранируем текст ссылки, но не трогаем URL
        parts.append(escape_markdown(link_text_part))
        parts.append(url_part)  # URL оставляем как есть
        parts.append(escape_markdown(closing_part))

        last_end = end

    # Добавляем оставшийся текст после последней ссылки
    if last_end < len(text):
        parts.append(escape_markdown(text[last_end:]))

    return "".join(parts)




def format_group_link(group):
    """
    Форматирует ссылку на группу в безопасном формате для MarkdownV2
    """
    if not hasattr(group, 'username') or not group.username:
        display_name = escape_markdown(str(group.group_id))
        url = escape_markdown(f"https://t.me/{group.group_id}")
    else:
        cleaned_username = group.username.lstrip('@')
        # Экранируем username, включая точки
        display_name = escape_markdown(group.username if group.username.startswith('@') else f"@{cleaned_username}")
        url = escape_markdown(f"https://t.me/{cleaned_username}")
    return f"[{display_name}]({url})"


def format_user_link(username: str | None, telegram_id: int) -> str:
    """
    Формирует MarkdownV2-ссылку на пользователя Telegram.
    """
    if username:
        cleaned_username = username.lstrip('@')
        display = escape_markdown(f"@{cleaned_username}")
        url = escape_markdown(f"https://t.me/{cleaned_username}")
    else:
        display = escape_markdown(str(telegram_id))
        url = escape_markdown(f"tg://user?id={telegram_id}")
    return f"[{display}]({url})"