import re


def escape_markdown(text: str) -> str:
    """
    Экранирование специальных символов для MarkdownV2
    """
    if text is None:
        return ""

    text = str(text)

    # Список символов для экранирования
    markdown_escape_chars = '_*[]()~`>#+-=|{}.!'

    # Экранируем каждый специальный символ
    escaped_text = ''.join(['\\' + char if char in markdown_escape_chars else char for char in text])

    return escaped_text


