# Команда normalize_subtopics

Утилита для наведения порядка в подтемах:

```bash
docker compose run --rm quiz_backend python manage.py normalize_subtopics
```

- По умолчанию работает в режиме dry-run и выводит список групп, где названия подтем совпадают после нормализации (например, «Functions and Arguments» и «Functions & Arguments»).
- Для применения изменений добавьте `--apply`. Команда выполнит всё в транзакции:
  - нормализует выбранное каноническое название;
  - переназначит все связанные `tasks.Task` на каноническую подтему;
  - удалит дубликаты.

Рекомендуемый порядок:

1. `docker compose run --rm quiz_backend python manage.py normalize_subtopics`
2. Проверить вывод и при необходимости скорректировать данные вручную.
3. `docker compose run --rm quiz_backend python manage.py normalize_subtopics --apply`

После применения перезапустите сервисы или очистите кэш, чтобы новые названия подтем попали в выдачу мини-приложения и API.

