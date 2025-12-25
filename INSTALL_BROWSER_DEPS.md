# Установка зависимостей для браузерной автоматизации

## Установка Python пакетов

```bash
cd quiz_backend
pip install playwright==1.40.0 selenium==4.15.0 undetected-chromedriver==3.5.4
```

Или из requirements.txt (если используете виртуальное окружение):

```bash
pip install -r ../requirements.txt
```

## Установка браузеров для Playwright

После установки `playwright` нужно установить браузеры:

```bash
playwright install chromium
playwright install firefox  # опционально
```

## Проверка установки

```bash
python3 -c "import playwright; print('playwright OK')"
python3 -c "import selenium; print('selenium OK')"
python3 -c "import undetected_chromedriver; print('undetected-chromedriver OK')"
```

## Если используете Docker

Добавьте в Dockerfile:

```dockerfile
# Установка зависимостей
RUN pip install playwright==1.40.0 selenium==4.15.0 undetected-chromedriver==3.5.4

# Установка браузеров Playwright
RUN playwright install chromium
RUN playwright install-deps chromium  # для системных зависимостей (если нужно)
```

## Системные зависимости (для Linux)

Если на Linux и используете Playwright, могут понадобиться системные зависимости:

```bash
# Ubuntu/Debian
sudo apt-get install -y \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2

# Или используйте команду Playwright:
playwright install-deps chromium
```

