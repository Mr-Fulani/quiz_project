# Команда для синхронизации полей социальных сетей существующих пользователей

Если нужно синхронизировать поля социальных сетей для уже существующих пользователей,
можно выполнить команду Django:

```bash
docker compose -f docker-compose.local-prod.yml run --rm web python manage.py shell
```

Затем в shell:
```python
from django.contrib.auth import get_user_model
from social_auth.services import TelegramAuthService

User = get_user_model()
users = User.objects.filter(social_accounts__is_active=True).distinct()
synced_count = 0

for user in users:
    if TelegramAuthService._sync_social_fields_from_accounts(user):
        synced_count += 1
        print(f"Синхронизирован пользователь: {user.username}")

print(f"Всего синхронизировано: {synced_count} пользователей")
```

Или можно создать management команду для этого.
