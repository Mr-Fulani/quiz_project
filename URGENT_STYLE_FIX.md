# 🚨 СРОЧНОЕ ИСПРАВЛЕНИЕ СТИЛЕЙ

## 📋 Проблема
Стили на продакшене отличаются от локальной версии (светлая тема вместо темной).

## 🔧 Быстрое решение

### Вариант 1: Диагностика + исправление

```bash
# 1. Диагностика проблемы
./debug_styles.sh

# 2. Принудительное исправление
./force_fix_styles.sh

# 3. В браузере жесткая перезагрузка
# Ctrl+Shift+R или Cmd+Shift+R
```

### Вариант 2: Только исправление

```bash
# Принудительное исправление
./force_fix_styles.sh
```

### Вариант 3: Полная пересборка

```bash
# Полная пересборка с нуля
docker compose -f docker-compose.local-prod.yml down -v
docker compose -f docker-compose.local-prod.yml up -d --build --force-recreate

# Очистка кэша
./clear_cache.sh
```

## 🔍 Что проверить

### 1. В браузере (DevTools):
1. Откройте **F12** → **Network**
2. Включите **"Disable cache"**
3. Обновите страницу **Ctrl+Shift+R**
4. Найдите CSS файл → проверьте **Headers**:
   - Имя должно содержать хеш: `style.abc123.css`
   - `Cache-Control: public, immutable`

### 2. На сервере:
```bash
# Проверка манифеста
docker compose -f docker-compose.local-prod.yml exec quiz_backend cat staticfiles/staticfiles.json | head -20

# Проверка версионированных файлов
docker compose -f docker-compose.local-prod.yml exec quiz_backend find staticfiles -name "*.css" | head -5
```

## 🎯 Ожидаемый результат

После исправления:
- ✅ Темная тема с зелеными акцентами
- ✅ Робот с шапкой выпускника
- ✅ "Development & Other"
- ✅ "@Mr_Fulani_Dev"
- ✅ Правильный рейтинг

## 🆘 Если не помогло

1. **Попробуйте режим инкогнито**
2. **Очистите кэш браузера полностью**
3. **Проверьте, что файлы действительно версионированы**
4. **Убедитесь, что мини-приложение использует правильные стили**

---

**Команда для выполнения на сервере:**
```bash
./force_fix_styles.sh
```
