# quiz_backend/Dockerfile


FROM python:3.11-slim


# Устанавливаем gettext
RUN apt-get update && apt-get install -y gettext && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Установить системные зависимости
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    postgresql-client \
    ffmpeg \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    libavutil-dev \
    # Зависимости для weasyprint (генерация PDF)
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    python3-cffi \
    python3-brotli \
    curl \
    && apt-get clean

# Установить зависимости Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копировать код Django
RUN mkdir -p /app/templates
COPY . /app/
COPY templates /app/templates

# Копируем entrypoint скрипт
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Создаем непривилегированного пользователя для Celery worker (безопасность)
RUN useradd -m -u 1000 celeryuser && \
    chown -R celeryuser:celeryuser /app

# Команда по умолчанию
CMD ["/entrypoint.sh"]


