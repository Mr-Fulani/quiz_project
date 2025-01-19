FROM python:3.12-slim

# Устанавливаем рабочую директорию
WORKDIR /mini_app

# Устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем все файлы приложения
COPY . .

# Создаем директории для статических файлов
RUN mkdir -p static/css static/js static/images

# Указываем порт и точку входа
EXPOSE 8080
CMD ["python", "app.py"]