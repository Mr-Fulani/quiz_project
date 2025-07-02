# Скрипты для автоматизации

## Загрузка иконок тем

### Описание
Скрипты для автоматической загрузки иконок из папки `static/blog/images/icons` в базу данных для тем опросов.

### Файлы
- `load_icons.py` - Django management-команда для загрузки иконок
- `wait_for_db.py` - Django management-команда для ожидания готовности БД
- `load_icons.sh` - Bash-скрипт для автоматического запуска в Docker

### Использование

#### Локально
```bash
cd quiz_backend
python manage.py load_icons
```

#### С опциями
```bash
# Показать что будет изменено, но не применять
python manage.py load_icons --dry-run

# Принудительно обновить все иконки
python manage.py load_icons --force

# Комбинация опций
python manage.py load_icons --dry-run --force
```

#### В Docker
```bash
# Запуск скрипта в контейнере
docker-compose exec web ./scripts/load_icons.sh

# Или через management-команду
docker-compose exec web python manage.py load_icons
```

### Логика сопоставления

Скрипт автоматически сопоставляет файлы иконок с темами по имени:

| Файл иконки | Тема в БД |
|-------------|-----------|
| `python-icon.png` | Python |
| `java-icon.png` | Java |
| `cpp-icon.png` | C++ |
| `javascript-icon.png` | JavaScript |
| `golang-icon.png` | Golang |

### Формат имен файлов
- Поддерживаемые форматы: `.png`, `.jpg`, `.jpeg`, `.svg`, `.gif`
- Рекомендуемый формат: `{theme-name}-icon.{extension}`
- Примеры: `python-icon.png`, `java-icon.svg`

### Автоматизация в Docker

Для автоматического запуска при деплое добавьте в `docker-compose.yml`:

```yaml
services:
  web:
    # ... другие настройки
    command: >
      sh -c "
        python manage.py wait_for_db &&
        python manage.py migrate &&
        python manage.py load_icons &&
        gunicorn config.wsgi:application --bind 0.0.0.0:8000
      "
```

### Мониторинг

Скрипт выводит подробную информацию:
- Количество найденных файлов иконок
- Сопоставление файлов с темами
- Статистику обновлений
- Список тем без иконок

### Пример вывода
```
🎨 Начинаю загрузку иконок для тем...
📁 Найдено 25 файлов иконок
📚 Найдено 15 тем в БД

🔍 Сопоставление иконок с темами:
  Python → python-icon.png
  Java → java-icon.png
  C++ → cpp-icon.png
  ...

✅ Обновлено: Python → /static/blog/images/icons/python-icon.png
✅ Обновлено: Java → /static/blog/images/icons/java-icon.png
❌ Не найдена иконка для темы: React

📊 Итоговая статистика:
  - Всего тем: 15
  - Обновлено: 14
  - Пропущено: 0
  - Не найдено иконок: 1

✅ Загрузка иконок завершена! 