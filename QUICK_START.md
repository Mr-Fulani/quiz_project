# 🚀 Быстрый старт

## Запуск продакшена (с автоматической очисткой кэша)

```bash
./start-prod.sh
```

**Что делает этот скрипт:**
1. ✅ Останавливает все контейнеры
2. ✅ Очищает неиспользуемые Docker-образы
3. ✅ Запускает все сервисы с SSL сертификатами
4. ✅ **Автоматически очищает и пересобирает кэш статических файлов с версионированием**
5. ✅ Перезапускает Nginx
6. ✅ Проверяет корректность сборки статики

**После запуска:**
- Откройте сайт в браузере
- Нажмите **Ctrl+Shift+R** (Windows/Linux) или **Cmd+Shift+R** (macOS)
- Готово! Все стили обновлены 🎉

---

## Запуск локальной разработки

```bash
./start-local.sh
```

**Примечание:** В режиме локальной разработки (DEBUG=True) кэширование отключено, стили обновляются автоматически.

---

## Обновление только стилей (без полного перезапуска)

### Для продакшена:

```bash
./clear_cache.sh
```

### Для локальной разработки:

```bash
./clear_cache_local.sh
```

Затем в браузере: **Ctrl+Shift+R** (или **Cmd+Shift+R**)

---

## Типичный workflow после git pull

### На сервере (продакшен):

```bash
# 1. Получаем последние изменения
git pull origin main

# 2. Перезапускаем продакшен (с автоматической очисткой кэша)
./start-prod.sh

# 3. В браузере жесткая перезагрузка
# Ctrl+Shift+R (или Cmd+Shift+R)
```

### Локально:

```bash
# 1. Получаем последние изменения
git pull origin main

# 2. Перезапускаем контейнеры
./start-local.sh

# 3. Стили обновятся автоматически (DEBUG=True)
```

---

## Проверка, что все работает

### 1. Проверка статики в контейнере:

```bash
# Для продакшена
docker compose -f docker-compose.local-prod.yml exec quiz_backend ls -la staticfiles/ | head -20

# Для локальной разработки
docker compose exec quiz_backend ls -la staticfiles/ | head -20
```

### 2. Проверка манифеста версионирования (только продакшен):

```bash
docker compose -f docker-compose.local-prod.yml exec quiz_backend cat staticfiles/staticfiles.json | head -30
```

Вы должны увидеть файлы с хешами:
```json
{
  "admin/css/base.css": "admin/css/base.abc123def456.css",
  "admin/js/vendor.js": "admin/js/vendor.789xyz012.js"
}
```

### 3. Проверка заголовков кэширования:

Откройте **DevTools (F12)** → **Network** → обновите страницу → кликните на CSS файл → посмотрите **Headers**:

```
Cache-Control: public, immutable
Expires: (дата через год для версионированных файлов)
```

---

## ⚠️ Устранение проблем

### Проблема: Стили не обновляются

**Решение 1:** Запустите скрипт очистки кэша
```bash
./clear_cache.sh  # для продакшена
```

**Решение 2:** Полная пересборка
```bash
docker compose -f docker-compose.local-prod.yml down -v
./start-prod.sh
```

**Решение 3:** Очистка кэша браузера
- Откройте режим инкогнито
- Или DevTools (F12) → Network → включите "Disable cache" → Ctrl+Shift+R

### Проблема: Ошибка при сборке статики

```bash
# Посмотрите подробные логи
docker compose -f docker-compose.local-prod.yml logs quiz_backend | tail -50

# Попробуйте собрать вручную с детализацией
docker compose -f docker-compose.local-prod.yml exec quiz_backend python manage.py collectstatic --noinput --clear -v 2
```

### Проблема: Права доступа

```bash
docker compose -f docker-compose.local-prod.yml exec quiz_backend chmod -R 755 staticfiles/
```

---

## 📚 Дополнительная документация

- **STATIC_FILES_CACHE.md** - полная документация по кэшированию статических файлов
- **APPLY_CACHE_FIX.md** - пошаговая инструкция по применению исправлений
- **DEPLOYMENT.md** - общая документация по деплою

