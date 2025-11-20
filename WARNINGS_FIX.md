# Исправление предупреждений системы

## Обзор предупреждений

В логах могут появляться следующие предупреждения:

### 1. PostgreSQL Collation Version Mismatch ⚠️

**Предупреждение:**
```
WARNING: database "fulani_quiz_db" has a collation version mismatch
DETAIL: The database was created using collation version 2.36, but the operating system provides version 2.41.
HINT: Rebuild all objects in this database that use the default collation and run ALTER DATABASE fulani_quiz_db REFRESH COLLATION VERSION
```

**Причина:** База данных была создана с одной версией collation, а система обновилась до новой версии.

**Решение:**
Автоматически исправляется при запуске через `./start-prod.sh`. Если нужно исправить вручную:

```bash
./fix-warnings.sh
```

Или вручную:
```bash
docker exec -e PGPASSWORD="$DB_PASSWORD" postgres_db_local_prod \
    psql -U "$DB_USER" -d "$DB_NAME" -c "ALTER DATABASE $DB_NAME REFRESH COLLATION VERSION;"
```

**Статус:** ✅ Автоматически исправляется при запуске

---

### 2. Redis Memory Overcommit ⚠️

**Предупреждение:**
```
WARNING Memory overcommit must be enabled! Without it, a background save or replication may fail under low memory condition.
```

**Причина:** На хосте отключён memory overcommit для Redis.

**Решение:**
Выполните на сервере (хосте):

```bash
sudo sysctl vm.overcommit_memory=1
sudo echo 'vm.overcommit_memory=1' >> /etc/sysctl.conf
```

**Статус:** ⚠️ Требует ручного исправления на хосте

---

### 3. Redis Security Attack Detection ⚠️

**Предупреждение:**
```
Possible SECURITY ATTACK detected. It looks like somebody is sending POST or Host: commands to Redis.
```

**Причина:** Сканеры или боты пытаются подключиться к Redis порту через HTTP-запросы. Это ложные срабатывания, если Redis защищён.

**Решение:**
1. **Убедитесь, что Redis доступен только внутри Docker сети:**
   - Redis должен быть доступен только через внутреннюю Docker сеть
   - Порт 6379 не должен быть открыт для публичного доступа (или защищён firewall)

2. **Настройте firewall на сервере:**
   ```bash
   # Запретить внешний доступ к Redis (только локальные подключения)
   sudo ufw deny 6379/tcp
   # Или разрешить только с определённых IP
   sudo ufw allow from <trusted-ip> to any port 6379
   ```

3. **Добавьте requirepass для Redis (опционально):**
   В `docker-compose.local-prod.yml` измените команду Redis:
   ```yaml
   redis:
     command: redis-server --maxmemory 512mb --maxmemory-policy allkeys-lru --save "" --requirepass ${REDIS_PASSWORD:-your-secure-password}
   ```
   И обновите переменные окружения в приложениях для использования пароля.

**Статус:** ⚠️ Требует проверки конфигурации сети/firewall

---

### 4. PostgreSQL Authentication Failures ⚠️

**Предупреждение:**
```
FATAL: password authentication failed for user "administrator"
DETAIL: Role "administrator" does not exist.
```

**Причина:** Сканеры или боты пытаются подключиться к PostgreSQL с распространёнными учётными данными (например, "administrator").

**Решение:**
1. **Убедитесь, что PostgreSQL доступен только внутри Docker сети:**
   - Порт 5433 не должен быть открыт для публичного доступа без защиты

2. **Настройте firewall:**
   ```bash
   # Запретить внешний доступ к PostgreSQL
   sudo ufw deny 5433/tcp
   # Или разрешить только с определённых IP
   sudo ufw allow from <trusted-ip> to any port 5433
   ```

3. **Используйте нестандартный порт (опционально):**
   Измените проброс порта в `docker-compose.local-prod.yml` на нестандартный.

**Статус:** ⚠️ Нормально для интернет-доступных портов (попытки сканирования), рекомендуется защита через firewall

---

## Быстрое исправление всех предупреждений

### Автоматическое исправление

Запустите скрипт:
```bash
./fix-warnings.sh
```

Этот скрипт исправит:
- ✅ Collation version mismatch (если контейнер запущен)
- ⚠️ Выведет инструкции для остальных предупреждений

### Ручное исправление

1. **PostgreSQL collation version:**
   ```bash
   docker exec -e PGPASSWORD="$DB_PASSWORD" postgres_db_local_prod \
       psql -U "$DB_USER" -d "$DB_NAME" -c "ALTER DATABASE $DB_NAME REFRESH COLLATION VERSION;"
   ```

2. **Redis memory overcommit:**
   ```bash
   sudo sysctl vm.overcommit_memory=1
   sudo echo 'vm.overcommit_memory=1' >> /etc/sysctl.conf
   ```

3. **Firewall настройки:**
   ```bash
   # Защита Redis
   sudo ufw deny 6379/tcp
   
   # Защита PostgreSQL (если не нужен внешний доступ)
   sudo ufw deny 5433/tcp
   ```

---

## Важные замечания

1. **Предупреждения о collation version** не критичны, но их стоит исправить для чистоты логов.

2. **Предупреждения Redis и PostgreSQL о безопасности** обычно не критичны, если сервисы защищены firewall и доступны только внутри Docker сети.

3. **Ошибки аутентификации** - это нормально для публично доступных портов, они показывают попытки сканирования.

4. **Memory overcommit** для Redis рекомендуется включить для предотвращения возможных проблем при нехватке памяти.

---

## Проверка после исправления

После исправления проверьте логи:
```bash
docker compose -f docker-compose.local-prod.yml logs postgres_db redis | grep -i warning
```

Предупреждения о collation version должны исчезнуть после первого подключения к БД.

