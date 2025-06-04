# quiz_backend/Dockerfile


FROM python:3.11-slim


# Устанавливаем gettext
RUN apt-get update && apt-get install -y gettext && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Установить системные зависимости
RUN apt-get update && apt-get install -y build-essential libpq-dev postgresql-client && apt-get clean

# Установить зависимости Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копировать код Django
RUN mkdir -p /app/templates
COPY . /app/
COPY templates /app/templates

# Команда по умолчанию
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]


