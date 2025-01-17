FROM python:3.12-slim

# Устанавливаем рабочую директорию
WORKDIR /mini_app

# Устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY . .

# Указываем порт и точку входа
EXPOSE 5000
CMD ["python", "app.py"]