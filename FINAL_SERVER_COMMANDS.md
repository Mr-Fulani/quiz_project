# Финальные команды для удаленного сервера

## Все ветки объединены в main

Выполните эти команды на удаленном сервере:

```bash
# 1. Перейти в директорию проекта
cd /opt/quiz_project/quiz_project

# 2. Переключиться на main и получить последние изменения
git checkout main
git pull origin main

# 3. Очистить устаревшие ссылки на удаленные ветки
git fetch --prune

# 4. Проверить что остались только нужные ветки
git branch -a
# Должны быть: main, security-updates-backup, remotes/origin/main, remotes/origin/security-updates-backup

# 5. Пересобрать контейнеры с новыми изменениями
docker compose -f docker-compose.local-prod.yml down
docker compose -f docker-compose.local-prod.yml up -d --build

# 6. Проверить логи что все запустилось корректно
docker compose -f docker-compose.local-prod.yml logs -f --tail=100 quiz_backend
```

## Что будет применено после пересборки

✅ Исправления Telegram авторизации:
   - RawPostDataException исправлен
   - Загрузка аватарки из Telegram
   - Корректное заполнение полей (first_name, last_name, username)

✅ Связывание пользователей:
   - MiniAppUser автоматически связывается с CustomUser
   - Обновление данных MiniAppUser при авторизации через сайт
   - Поиск существующих пользователей по username

✅ Объединение статистики:
   - Автоматическое объединение статистики Mini App с основной
   - При связывании аккаунтов статистика объединяется

## Важно

После пересборки контейнеров все изменения будут активны. Рекомендуется протестировать авторизацию через Telegram.

