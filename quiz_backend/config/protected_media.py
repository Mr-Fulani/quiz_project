"""
Раздача приватных файлов из MEDIA_ROOT после проверки доступа во view.

В продакшене файл отдаёт nginx: Django отвечает заголовком X-Accel-Redirect на internal-локацию
/protected-media/ (alias на /app/media/, см. nginx/nginx-prod.conf), а прямые пути к приватным
каталогам в /media/ закрыты. В DEBUG (без nginx) файл отдаёт сам Django.
"""
import os

from django.conf import settings
from django.http import FileResponse, HttpResponse
from django.utils.http import content_disposition_header

PROTECTED_MEDIA_PREFIX = '/protected-media/'


def serve_protected_file(field_file, filename=None, as_attachment=True):
    """Ответ с файлом FileField; filename — имя для пользователя (по умолчанию имя файла)."""
    display_name = filename or os.path.basename(field_file.name)
    if settings.DEBUG:
        response = FileResponse(field_file)
    else:
        response = HttpResponse()
        response['X-Accel-Redirect'] = f"{PROTECTED_MEDIA_PREFIX}{field_file.name}"
        response['Content-Type'] = ''  # тип определит nginx по расширению
    response['Content-Disposition'] = content_disposition_header(as_attachment, display_name)
    response['X-Content-Type-Options'] = 'nosniff'
    response['Cache-Control'] = 'private, no-store'
    return response
