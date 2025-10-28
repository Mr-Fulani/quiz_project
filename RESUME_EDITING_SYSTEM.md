# Система редактирования резюме

## Обзор

Реализована полноценная система хранения и редактирования резюме с сохранением данных в базе данных PostgreSQL.

## Что сделано

### 1. Модель данных (`blog/models.py`)

Создана модель `Resume` с полями:
- **Основная информация**: `name`, `is_active`
- **Контакты**: `contact_info_en`, `contact_info_ru`, `email`, `websites` (JSON)
- **Профессиональное резюме**: `summary_en`, `summary_ru`
- **Навыки**: `skills` (JSON array)
- **История работы**: `work_history` (JSON array с объектами)
- **Образование**: `education` (JSON array с объектами)
- **Языки**: `languages` (JSON array с объектами)

**Особенности:**
- Только одно резюме может быть активным одновременно
- JSON поля позволяют хранить списки и сложные структуры
- Автоматическая деактивация других резюме при создании нового активного

### 2. Django Admin (`blog/admin.py`)

Добавлена админ-панель `ResumeAdmin` для управления резюме через Django Admin:
- Удобное редактирование всех полей
- Группировка полей по секциям
- Подсказки по формату JSON данных
- Поиск по имени, email, тексту резюме
- Фильтрация по статусу активности и датам

**Доступ:** `/admin/blog/resume/`

### 3. API Endpoint (`blog/api/api_views.py`)

Создан API endpoint для сохранения резюме через интерфейс сайта:

**URL:** `/api/resume/save/`  
**Метод:** `POST`  
**Права:** Только администраторы (`IsAdminUser`)

**Формат запроса:**
```json
{
  "name": "Anvar Sharipov",
  "contact_info_en": "Istanbul, Turkey...",
  "contact_info_ru": "Стамбул, Турция...",
  "email": "fulani.dev@gmail.com",
  "websites": ["https://github.com/...", "https://t.me/..."],
  "summary_en": "Professional summary...",
  "summary_ru": "Профессиональное резюме...",
  "skills": ["Python", "Django", "Docker"],
  "work_history": [{
    "title_en": "...",
    "title_ru": "...",
    "period_en": "...",
    "period_ru": "...",
    "company_en": "...",
    "company_ru": "...",
    "responsibilities_en": ["...", "..."],
    "responsibilities_ru": ["...", "..."]
  }]
}
```

### 4. View для загрузки данных (`blog/views.py`)

Обновлен `ResumeView` для загрузки активного резюме из БД:
```python
resume = Resume.objects.filter(is_active=True).first()
context['resume'] = resume
```

### 5. JavaScript с отправкой на сервер (`blog/static/blog/js/resume.js`)

Обновлен обработчик формы:
- Собирает данные из формы
- Отправляет POST запрос на `/api/resume/save/`
- Обрабатывает CSRF токены
- Обновляет DOM после успешного сохранения
- Показывает сообщения об ошибках

### 6. Шаблон с загрузкой из БД (`blog/templates/blog/resume.html`)

Обновлен шаблон для загрузки данных из контекста:
- Использует `{{ resume.field|default:'...' }}` для всех полей
- Поддерживает fallback на захардкоженные значения
- Динамическая генерация списков из JSON полей

### 7. Management команда для импорта (`blog/management/commands/import_resume.py`)

Создана команда для импорта текущих данных резюме в БД:
```bash
docker compose run quiz_backend python manage.py import_resume
```

**Что импортируется:**
- Все текущие данные из шаблона
- 3 записи в Work History
- 1 запись в Education
- 4 языка
- 8 навыков

## Как использовать

### Редактирование через интерфейс сайта

1. Авторизуйтесь как администратор (staff user)
2. Откройте страницу `/resume/`
3. Нажмите кнопку "Edit" 
4. Отредактируйте поля в модальном окне
5. Нажмите "Save Changes"
6. Данные сохраняются в БД и отображаются на странице

**Примечание:** После перезагрузки страницы данные загружаются из БД!

### Редактирование через Django Admin

1. Откройте `/admin/blog/resume/`
2. Выберите активное резюме или создайте новое
3. Отредактируйте любые поля (включая JSON)
4. Сохраните
5. Изменения сразу отображаются на странице `/resume/`

**Формат JSON полей:**

```python
# websites
["https://github.com/...", "https://t.me/..."]

# skills
["Python", "Django", "Docker", "PostgreSQL"]

# work_history
[{
  "title_en": "Senior Developer",
  "title_ru": "Старший разработчик",
  "period_en": "2023 to Current",
  "period_ru": "2023 по настоящее время",
  "company_en": "Company Name",
  "company_ru": "Название компании",
  "responsibilities_en": ["Task 1", "Task 2"],
  "responsibilities_ru": ["Задача 1", "Задача 2"]
}]

# education
[{
  "title_en": "Master of Science",
  "title_ru": "Магистр наук",
  "period_en": "2020",
  "period_ru": "2020",
  "institution_en": "University Name",
  "institution_ru": "Название университета"
}]

# languages
[{
  "name_en": "English: Fluent",
  "name_ru": "Английский: Свободно",
  "level": 90
}]
```

## Преимущества нового подхода

✅ **Сохранение данных в БД** - данные не теряются после перезагрузки  
✅ **Гибкое редактирование** - два способа: через сайт и через админку  
✅ **Поддержка двух языков** - EN и RU версии для всех полей  
✅ **JSON поля** - легко добавлять/удалять записи  
✅ **Версионирование** - можно создавать несколько резюме и переключаться между ними  
✅ **API** - легко интегрировать с другими системами  
✅ **Безопасность** - редактирование только для администраторов

## Миграции

```bash
# Создание миграции
docker compose run quiz_backend python manage.py makemigrations blog

# Применение миграции
docker compose run quiz_backend python manage.py migrate blog

# Импорт данных
docker compose run quiz_backend python manage.py import_resume
```

## Будущие улучшения

- [ ] Добавить редактирование всех записей Work History (сейчас только первая)
- [ ] Добавить редактирование Education через интерфейс
- [ ] Добавить редактирование Languages через интерфейс  
- [ ] Добавить WYSIWYG редактор для текстовых полей
- [ ] Добавить историю изменений (версионирование)
- [ ] Добавить экспорт в PDF с данными из БД
- [ ] Добавить preview перед сохранением

## Технические детали

**Технологии:**
- Django 4.x
- PostgreSQL
- Django REST Framework
- JSON поля для гибкого хранения данных
- CSRF защита для API
- Permissions (IsAdminUser) для безопасности

**Файлы, которые были изменены:**
1. `quiz_backend/blog/models.py` - модель Resume
2. `quiz_backend/blog/admin.py` - админка ResumeAdmin
3. `quiz_backend/blog/views.py` - загрузка из БД в ResumeView
4. `quiz_backend/blog/api/api_views.py` - API endpoint save_resume_api
5. `quiz_backend/blog/api/api_urls.py` - URL для API
6. `quiz_backend/blog/static/blog/js/resume.js` - отправка на сервер
7. `quiz_backend/blog/templates/blog/resume.html` - загрузка из контекста
8. `quiz_backend/blog/management/commands/import_resume.py` - команда импорта

**Новые файлы:**
- `blog/migrations/0006_resume.py` - миграция для модели Resume
- `blog/management/commands/import_resume.py` - команда импорта

