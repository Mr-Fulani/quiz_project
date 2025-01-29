# quiz_backend/Dockerfile


FROM python:3.11-slim

WORKDIR /app

# Установить системные зависимости
RUN apt-get update && apt-get install -y build-essential libpq-dev postgresql-client && apt-get clean

# Установить зависимости Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копировать код Django
COPY . /app

# Команда по умолчанию
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]


