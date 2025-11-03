# Исправления предупреждений и ошибок

## 1. PostgreSQL Collation Version Mismatch

### Проблема
```
WARNING: database "fulani_quiz_db" has a collation version mismatch
DETAIL: The database was created using collation version 2.36, but the operating system provides version 2.41.
```

### Решение
Это предупреждение не критично, но рекомендуется обновить версию collation в базе данных:

```sql
-- Подключитесь к базе данных
psql -U postgres -d fulani_quiz_db

-- Обновите версию collation
ALTER DATABASE fulani_quiz_db REFRESH COLLATION VERSION;
```

**Важно:** Это безопасная операция, которая не влияет на данные, но может занять некоторое время на больших базах данных.

### Альтернативное решение
Если предупреждение не мешает работе, можно оставить как есть. PostgreSQL продолжит работать нормально, но может выдать предупреждения в логах.

---

## 2. Celery Worker Security Warning

### Проблема
```
SecurityWarning: You're running the worker with superuser privileges: this is absolutely not recommended!
```

### Решение
Исправлено в `quiz_backend/Dockerfile` и `docker-compose.local-prod.yml`:
- Создан непривилегированный пользователь `celeryuser` (UID 1000)
- Celery worker запускается от этого пользователя

**Примечание:** Если возникнут проблемы с правами доступа к volumes, убедитесь, что директории имеют правильные права:
```bash
chown -R 1000:1000 /path/to/volumes
```

---

## 3. Celery Broker Connection Retry Warning

### Проблема
```
CPendingDeprecationWarning: The broker_connection_retry configuration setting will no longer determine...
```

### Решение
Добавлена настройка в `quiz_backend/config/settings.py`:
```python
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
```

Это исправление подготовит проект к переходу на Celery 6.0+.

---

## 4. Redis Connection Error в Celery Beat

### Проблема
```
Error -2 connecting to redis_cache:6379. Name or service not known.
```

### Решение
Исправлено в `docker-compose.local-prod.yml`:
- Добавлена переменная `CELERY_RESULT_BACKEND=redis://redis_cache_prod:6379/0`
- Используется правильное имя сервиса `redis_cache_prod` вместо `redis_cache`

---

## 5. AWS S3 настройки для генерации изображений

### Проблема
Изображения не загружались в S3 при импорте задач через админку Django.

### Решение
Добавлены переменные окружения AWS S3 в `docker-compose.local-prod.yml`:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `S3_BUCKET_NAME`
- `S3_REGION`

Убедитесь, что эти переменные установлены в `.env` файле на сервере.

---

## 6. Ошибка с полем description в модели Subtopic

### Проблема
```
Invalid field name(s) for model Subtopic: 'description'
```

### Решение
Убрано несуществующее поле `description` из создания `Subtopic` в `task_import_service.py`.

---

## 7. Nginx: Deprecated listen http2 directive

### Проблема
```
nginx: [warn] the "listen ... http2" directive is deprecated, use the "http2" directive instead
```

### Решение
Исправлено в `nginx/nginx-prod.conf`:
- Заменен устаревший синтаксис `listen 443 ssl http2;` на новый:
  ```nginx
  listen 443 ssl;
  http2 on;
  ```

---

## 8. Nginx: Conflicting server name

### Проблема
```
nginx: [warn] conflicting server name "quiz-code.com" on 0.0.0.0:80, ignored
```

### Решение
Исправлено в `nginx/nginx-prod.conf`:
- Удалено дублирование server блоков для порта 80
- Объединены блоки верификации Let's Encrypt и редиректа HTTP → HTTPS в один

---

## 9. Redis: Memory overcommit warning

### Проблема
```
WARNING Memory overcommit must be enabled! Without it, a background save or replication may fail under low memory condition.
```

### Решение
Частично исправлено в `docker-compose.local-prod.yml`:
- Добавлен параметр `--save ""` для отключения автоматического сохранения (если не требуется persistence)
- Добавлены настройки `sysctls` для оптимизации

**Полное исправление требует настройки хоста:**
```bash
# На хосте выполните:
sudo sysctl vm.overcommit_memory=1

# Для постоянного применения добавьте в /etc/sysctl.conf:
vm.overcommit_memory = 1
```

**Примечание:** Это предупреждение не критично для работы Redis в контейнере, но рекомендуется исправить для production окружения.

---

## Применение исправлений

После применения исправлений:

1. Пересоберите контейнеры:
   ```bash
   docker compose -f docker-compose.local-prod.yml build
   ```

2. Перезапустите сервисы:
   ```bash
   docker compose -f docker-compose.local-prod.yml up -d
   ```

3. Проверьте логи:
   ```bash
   docker compose -f docker-compose.local-prod.yml logs celery_worker_prod
   docker compose -f docker-compose.local-prod.yml logs celery_beat_prod
   ```

