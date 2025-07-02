# Автоматизация для продакшена

## Загрузка иконок тем

### Что происходит автоматически при деплое

При запуске контейнера `quiz_backend` автоматически выполняются следующие шаги:

1. **Ожидание готовности БД** - `python manage.py wait_for_db`
2. **Применение миграций** - `python manage.py migrate`
3. **Сбор статических файлов** - `python manage.py collectstatic --noinput`
4. **Загрузка иконок в БД** - `python manage.py load_icons --skip-existing`
5. **Запуск Django сервера** - `python manage.py runserver 0.0.0.0:8000`

### Файлы автоматизации

- `entrypoint.sh` - основной скрипт запуска
- `topics/management/commands/load_icons.py` - команда загрузки иконок
- `blog/management/commands/wait_for_db.py` - команда ожидания БД

### Логика работы

1. **Сбор статики**: Django копирует файлы из `blog/static/` в `staticfiles/`
2. **Загрузка иконок**: Скрипт сканирует `staticfiles/blog/images/icons/` и сопоставляет с темами
3. **Обновление БД**: Для каждой темы обновляется поле `icon` с правильным путем

### Для продакшена

При деплое на продакшен с чистой БД:

```bash
# Пересборка и запуск
docker-compose down
docker-compose build quiz_backend
docker-compose up -d

# Проверка логов
docker-compose logs quiz_backend
```

### Проверка результата

После успешного деплоя в логах должно быть:

```
🚀 Запуск Django приложения...
⏳ Ожидание готовности базы данных...
✅ База данных готова!
🔄 Применение миграций...
📁 Сбор статических файлов...
🎨 Загрузка иконок для тем...
📁 Найдено 25 файлов иконок
📚 Найдено 15 тем в БД
✅ Обновлено: Python → /static/blog/images/icons/python-icon.png
...
✅ Загрузка иконок завершена!
🌐 Запуск Django сервера...
```

### Ручной запуск (если нужно)

```bash
# Только загрузка иконок (пропуская уже установленные)
docker exec quiz_backend python manage.py load_icons --skip-existing

# Принудительное обновление всех иконок
docker exec quiz_backend python manage.py load_icons --force

# Полное обновление (сбор статики + принудительная загрузка)
docker exec quiz_backend ./scripts/update_icons.sh

# Сбор статики + загрузка иконок
docker exec quiz_backend bash -c "python manage.py collectstatic --noinput && python manage.py load_icons"
```

### Мониторинг

- Проверяйте логи контейнера: `docker-compose logs quiz_backend`
- Проверяйте наличие иконок в БД через Django admin
- Проверяйте отображение иконок на сайте 