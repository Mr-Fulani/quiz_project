FROM python:3.12-slim

# Устанавливаем рабочую директорию
WORKDIR /mini_app

# Устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Создаем все необходимые директории
RUN mkdir -p static/css static/js static/images

# Копируем статические файлы
COPY static/css/* static/css/
COPY static/js/* static/js/
COPY static/images/* static/images/

# Копируем шаблоны
COPY templates/* templates/

# Копируем остальные файлы
COPY app.py .

# Указываем порт и команду запуска
EXPOSE 8080

# Добавляем флаг --reload для разработки
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080", "--reload", "--log-level", "debug"]