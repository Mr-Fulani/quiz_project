# 🚨 Экстренная инструкция для перегруженного сервера

## Ситуация

Ваш сервер `vm4286169` критически перегружен:
- **RAM: 95%** (1.9/2 GB) ⚠️
- **Storage: 94%** (37.5/40 GB) ⚠️
- **vCPU: 87%** ⚠️

Оптимизации кода помогли, но нужно **экстренно освободить ресурсы**.

## Порядок действий (выполняйте на продакшене)

### Шаг 1: Остановить и очистить Docker

```bash
# Перейти в директорию проекта
cd /opt/quiz_project/quiz_project

# Остановить все контейнеры
docker compose -f docker-compose.local-prod.yml down

# Удалить неиспользуемые образы и кэш
docker system prune -a --volumes -f

# Удалить старые неиспользуемые образы
docker image prune -a -f

# Удалить неиспользуемые volumes
docker volume prune -f
```

### Шаг 2: Проверить и очистить логи Docker

```bash
# Проверить размер логов
du -sh /var/lib/docker/containers/*/

# Очистить старые логи (ВАЖНО: потеряете историю логов)
truncate -s 0 /var/lib/docker/containers/*/*-json.log
```

### Шаг 3: Очистить систему

```bash
# Очистка apt кэша
apt-get clean
apt-get autoremove -y

# Проверить большие файлы
du -h / | sort -rh | head -20

# Проверить старые ядра
dpkg --list | grep linux-image

# Удалить старые ядра (замените X.X.X на версию старого ядра)
# apt-get remove --purge linux-image-X.X.X-generic
```

### Шаг 4: Получить последние изменения и запустить

```bash
# Перейти в директорию проекта
cd /opt/quiz_project/quiz_project

# Получить последние изменения
git pull origin main

# Запустить с минимальной нагрузкой (аварийный режим)
GUNICORN_WORKERS=1 GUNICORN_THREADS=1 ./start-prod.sh --fast
```

### Шаг 5 (опционально): Настроить Docker daemon

```bash
# Создать конфиг для ограничения логов
sudo nano /etc/docker/daemon.json
```

Добавить:
```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

```bash
# Перезапустить Docker
sudo systemctl restart docker
```

## Если все еще не запускается

### Вариант 1: Абсолютный минимум

Измените `docker-compose.local-prod.yml` временно:

```yaml
quiz_backend:
  environment:
    - GUNICORN_WORKERS=1  # ← уменьшить до 1
    - GUNICORN_THREADS=1   # ← уменьшить до 1

celery_worker:
  command: python -m celery -A config worker --loglevel=info --concurrency=1  # ← уменьшить с 4 до 1
```

### Вариант 2: Отключить ненужные сервисы

Если не нужны Celery/Redis для базовой работы:

```bash
# Запустить только самое необходимое
docker compose -f docker-compose.local-prod.yml up -d postgres_db nginx quiz_backend mini_app
```

### Вариант 3: Проверить swap

```bash
# Проверить swap
free -h
swapon --show

# Если нет swap, создать (на 4 GB сервере)
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Добавить в fstab для постоянства
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

## Мониторинг после запуска

```bash
# Проверить статус контейнеров
docker compose -f docker-compose.local-prod.yml ps

# Проверить логи
docker compose -f docker-compose.local-prod.yml logs quiz_backend --tail=50

# Проверить ресурсы
htop

# Или Docker stats
docker stats
```

## Рекомендации для долгосрочного решения

1. **Увеличить RAM**: минимум 4 GB (сейчас 2 GB)
2. **Увеличить диск**: минимум 60-80 GB (сейчас 40 GB)
3. **Добавить swap**: минимум 2-4 GB
4. **Мониторинг**: установить `htop`, `iotop`, `nethogs`

## Контакты и помощь

- Документация: `OPTIMIZATION_SUMMARY.md`
- Логи проекта: `quiz_backend/logs/`
- Docker логи: `/var/lib/docker/containers/`

## Примечания

⚠️ **ВНИМАНИЕ**: После очистки логов Docker вы потеряете историю логов.  
⚠️ **ВНИМАНИЕ**: Удаление старых ядер может быть необратимо.  
⚠️ **ВАЖНО**: Делайте резервные копии перед массовой очисткой.

