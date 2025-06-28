# quiz_project/mini_app/Dockerfile
FROM python:3.11-slim

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /mini_app

# Копируем файл зависимостей в рабочую директорию
COPY requirements.txt .

# Устанавливаем зависимости проекта
RUN pip install --no-cache-dir -r requirements.txt

# Создаём необходимые директории для статических файлов
RUN mkdir -p static/css static/js static/images uploads

# Копируем статические файлы
COPY static/css/* static/css/
COPY static/js/* static/js/
COPY static/images/* static/images/

# Копируем шаблоны
COPY templates/* templates/

# Копируем папки с кодом приложения
COPY routers/ routers/
COPY services/ services/
COPY core/ core/

# Копируем основной файл приложения
COPY app.py .

# Открываем порт, на котором будет работать приложение
EXPOSE 8080

# Команда для запуска приложения
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080", "--reload"]
