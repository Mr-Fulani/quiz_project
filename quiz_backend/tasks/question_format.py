"""
Как показывать вопрос задачи без картинки: окном редактора с кодом или текстовой карточкой.

Одно правило для сайта, Mini App и Telegram (у бота копия — bot/utils/question_format.py):
- тенант с темой оформления не «code» (например, islamic) — всегда текст;
- иначе вопрос с признаками кода — код с подсветкой языка темы; обычная фраза — текст;
- вопрос-фраза после кода («…Что вернёт этот endpoint?») выносится в подпись.
"""
import re

# Тема задачи → язык подсветки (highlight.js / Telegram)
CODE_LANGUAGES = {
    'python': 'python', 'django': 'python', 'fastapi': 'python', 'flask': 'python',
    'golang': 'go', 'go': 'go',
    'javascript': 'javascript', 'js': 'javascript', 'typescript': 'typescript', 'react': 'javascript',
    'java': 'java', 'kotlin': 'kotlin', 'c#': 'csharp', 'csharp': 'csharp', 'c++': 'cpp', 'cpp': 'cpp',
    'sql': 'sql', 'postgresql': 'sql', 'mysql': 'sql',
    'git': 'bash', 'bash': 'bash', 'linux': 'bash', 'docker': 'bash',
    'php': 'php', 'rust': 'rust', 'swift': 'swift', 'ruby': 'ruby',
}

_CODE_HINT = re.compile(
    r'[=;{}\[\]<>]|\w\(|\)\s*$|^\s*(def|class|import|from|return|print|func|package|var|let|const|public|'
    r'private|select|insert|update|delete|create|git|docker|console\.|fmt\.|system\.)\b|^\s*[@#$]',
    re.IGNORECASE | re.MULTILINE,
)
_INDENTED = re.compile(r'\n[ \t]{2,}\S')


def looks_like_code(text):
    text = (text or '').strip()
    if not text or ('\n' not in text and text.endswith('?')):
        return False  # однострочный вопрос-фраза, даже с кодом внутри: «What does len(x) return?»
    return bool(_INDENTED.search(text) or _CODE_HINT.search(text))


def _split_prompt(text):
    """Код и вопрос-фраза после него (последний абзац без признаков кода, заканчивается «?»)."""
    parts = re.split(r'\n\s*\n', text.strip())
    if len(parts) > 1:
        last = parts[-1].strip()
        if last.endswith('?') and '\n' not in last and not looks_like_code(last):
            return '\n\n'.join(parts[:-1]).rstrip(), last
    return text.strip(), None


def code_language(topic_name):
    return CODE_LANGUAGES.get((topic_name or '').strip().lower())


def question_display(task, question):
    """
    Возвращает словарь:
      kind: 'code' | 'text'; language: язык подсветки или None;
      body: код или текст вопроса; prompt: вопрос-подпись к коду или None; theme: тема оформления тенанта.
    """
    question = (question or '').replace('\r\n', '\n')
    tenant = getattr(task, 'tenant', None)
    theme = getattr(tenant, 'image_theme', None) or 'code'
    topic = getattr(task, 'topic', None)
    language = code_language(getattr(topic, 'name', None))

    if theme == 'code' and looks_like_code(question):
        body, prompt = _split_prompt(question)
        return {'kind': 'code', 'language': language, 'body': body, 'prompt': prompt, 'theme': theme}
    return {'kind': 'text', 'language': None, 'body': question.strip(), 'prompt': None, 'theme': theme}
