# Команды для слияния веток на удаленном сервере

## Команды для выполнения на удаленном сервере

Выполните эти команды на удаленном сервере в директории проекта:

```bash
# 1. Перейти в директорию проекта
cd /opt/quiz_project/quiz_project

# 2. Проверить текущую ветку и список веток
git branch -a
git status

# 3. Переключиться на основную ветку main
git checkout main

# 4. Получить последние изменения с удаленного репозитория
git fetch origin

# 5. Обновить локальную ветку main с удаленного сервера
git pull origin main

# 6. Удалить локальную ветку fix/telegram-auth-issue если она существует
git branch -D fix/telegram-auth-issue 2>/dev/null || echo "Ветка fix/telegram-auth-issue не существует локально"

# 7. Удалить удаленную ветку fix/telegram-auth-issue если она существует
git push origin --delete fix/telegram-auth-issue 2>/dev/null || echo "Ветка fix/telegram-auth-issue не существует на удаленном сервере"

# 8. Проверить что остались только нужные ветки (main и security-updates-backup)
git branch -a

# 9. Пересобрать контейнеры с новыми изменениями
docker compose -f docker-compose.local-prod.yml down
docker compose -f docker-compose.local-prod.yml up -d --build

# 10. Проверить логи что все запустилось корректно
docker compose -f docker-compose.local-prod.yml logs -f --tail=100 quiz_backend
```

## Ожидаемый результат

После выполнения команд должны остаться только ветки:
- `main` (основная ветка)
- `security-updates-backup` (ветка бэкапа)
- `remotes/origin/main`
- `remotes/origin/security-updates-backup`

Ветка `fix/telegram-auth-issue` должна быть удалена как локально, так и на удаленном сервере.

## Важно

- Все изменения из `fix/telegram-auth-issue` уже влиты в `main`
- После pull и пересборки контейнеров будут применены все исправления Telegram авторизации
- Новая ветка `feature/user-linking-and-stats-merge` создана локально для дальнейшей работы

