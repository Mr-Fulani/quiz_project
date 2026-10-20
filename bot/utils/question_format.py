"""
Как показывать вопрос задачи без картинки — копия quiz_backend/tasks/question_format.py для бота
(у бота нет Django). Меняя правило, меняйте оба файла.
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


def question_display(topic_name, question, theme='code'):
    """
    Словарь: kind 'code' | 'text', language, body (код или текст), prompt (вопрос-подпись к коду), theme.
    """
    question = (question or '').replace('\r\n', '\n')
    theme = theme or 'code'
    language = code_language(topic_name)
    if theme == 'code' and looks_like_code(question):
        body, prompt = _split_prompt(question)
        return {'kind': 'code', 'language': language, 'body': body, 'prompt': prompt, 'theme': theme}
    return {'kind': 'text', 'language': None, 'body': question.strip(), 'prompt': None, 'theme': theme}
