# ⚡ Быстрая инструкция: Применение исправлений кэширования

## 🎯 Что было исправлено?

✅ Добавлено версионирование статических файлов через `ManifestStaticFilesStorage`  
✅ Оптимизировано кэширование в Nginx  
✅ Создан скрипт для очистки кэша после деплоя  

---

## 🚀 Команды для применения изменений

### Вариант 1: На удаленном сервере (продакшен)

```bash
# 1. Перейдите в директорию проекта
cd /Users/user/telegram_quiz_bots/quiz_project

# 2. Остановите контейнеры
docker compose -f docker-compose.local-prod.yml down

# 3. Запустите с пересборкой
docker compose -f docker-compose.local-prod.yml up -d --build

# 4. Дождитесь полного запуска (30-60 секунд)
sleep 30

# 5. Проверьте, что статика собралась
docker compose -f docker-compose.local-prod.yml exec quiz_backend ls -la staticfiles/ | head -20

# 6. Проверьте, что появился манифест с хешами
docker compose -f docker-compose.local-prod.yml exec quiz_backend cat staticfiles/staticfiles.json | head -20
```

### Вариант 2: Локальная разработка

```bash
# 1. Перейдите в директорию проекта
cd /Users/user/telegram_quiz_bots/quiz_project

# 2. Остановите контейнеры
docker compose down

# 3. Запустите с пересборкой
docker compose up -d --build
```

---

## 🧹 После будущих обновлений кода

Каждый раз после `git pull` и обновления стилей:

```bash
# Используйте новый скрипт очистки кэша
./clear_cache.sh
```

Затем в браузере:
- **Windows/Linux:** `Ctrl + Shift + R`
- **macOS:** `Cmd + Shift + R`

---

## ✅ Проверка работы

1. **Откройте сайт в браузере**
2. **Откройте DevTools (F12)**
3. **Перейдите на вкладку Network**
4. **Обновите страницу**
5. **Найдите любой CSS файл**
6. **Проверьте:**
   - Имя файла должно содержать хеш (например, `style.abc123.css`)
   - В Headers должно быть: `Cache-Control: public, immutable`

---

## 🆘 Если что-то пошло не так

### Ошибка при сборке статики:

```bash
# Посмотрите логи
docker compose -f docker-compose.local-prod.yml logs quiz_backend

# Или попробуйте собрать вручную с подробным выводом
docker compose -f docker-compose.local-prod.yml exec quiz_backend python manage.py collectstatic --noinput --clear -v 2
```

### Стили все еще старые:

```bash
# Очистите кэш полностью
docker compose -f docker-compose.local-prod.yml down -v
docker compose -f docker-compose.local-prod.yml up -d --build

# В браузере откройте в режиме инкогнито
```

### Проблемы с правами доступа:

```bash
# Установите правильные права
docker compose -f docker-compose.local-prod.yml exec quiz_backend chmod -R 755 staticfiles/
```

---

## 📝 Важно знать

- **В режиме `DEBUG=True`** (локальная разработка) - все работает как раньше, кэширования нет
- **В режиме `DEBUG=False`** (продакшен) - используется версионирование и кэширование
- **После каждого `git pull`** - запускайте `./clear_cache.sh`
- **В CI/CD** - добавьте `python manage.py collectstatic --noinput --clear` после деплоя

---

## 📚 Подробная документация

Смотрите файл `STATIC_FILES_CACHE.md` для полной информации о проблеме и решении.

