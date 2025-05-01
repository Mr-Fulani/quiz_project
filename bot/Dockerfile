# bot/Dockerfile

FROM python:3.12-slim

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    fontconfig \
    fonts-dejavu \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию
WORKDIR /quiz_project

# Копируем файл зависимостей и устанавливаем их
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Копируем остальные файлы проекта
COPY . .

# Копируем папку fonts (если нужна)
COPY ./fonts /quiz_project/fonts

# Устанавливаем PYTHONPATH
ENV PYTHONPATH=/quiz_project

# Копируем entrypoint.sh в контейнер
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Указываем точку входа
ENTRYPOINT ["/entrypoint.sh"]

