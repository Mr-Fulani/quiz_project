FROM python:3.12-slim

# Устанавливаем системные зависимости (если нужны)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    fontconfig \
    fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию
WORKDIR /quiz_project

# Копируем файл зависимостей и устанавливаем их
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Копируем остальные файлы проекта
COPY . .

# Добавляем папку fonts в контейнер
COPY fonts /quiz_project/fonts

# Устанавливаем PYTHONPATH
ENV PYTHONPATH=/quiz_project

# Указываем команду по умолчанию
CMD ["python", "bot/main.py"]