# Функционал галереи аватарок пользователей

## Описание
Реализована возможность хранения и отображения до 3 аватарок (фото или GIF) для каждого пользователя Mini App. При клике на аватарку открывается модальное окно со свайпером для просмотра всех аватарок.

## Реализованный функционал

### Backend (Django)

#### 1. Модель данных
**Файл:** `quiz_backend/accounts/models.py`

- Создана модель `UserAvatar`:
  - `user` - ForeignKey на MiniAppUser
  - `image` - ImageField для хранения изображения
  - `order` - порядок отображения (0, 1, 2)
  - `created_at` - дата создания
  - Ограничение: максимум 3 аватарки на пользователя
  - Поддержка GIF файлов

#### 2. Serializers
**Файл:** `quiz_backend/accounts/serializers.py`

- `UserAvatarSerializer` - сериализатор для аватарок
- Обновлен `MiniAppUserSerializer` - добавлено поле `avatars` (список всех аватарок пользователя)

#### 3. API Endpoints
**Файл:** `quiz_backend/accounts/api/api_views.py`

Созданы views:
- `UserAvatarUploadView` - загрузка новой аватарки
- `UserAvatarDeleteView` - удаление аватарки
- `UserAvatarReorderView` - изменение порядка аватарок

**Файл:** `quiz_backend/accounts/api/api_urls.py`

URL-паттерны:
- `POST /api/accounts/miniapp-users/{telegram_id}/avatars/` - загрузка
- `DELETE /api/accounts/miniapp-users/{telegram_id}/avatars/{avatar_id}/` - удаление
- `PATCH /api/accounts/miniapp-users/{telegram_id}/avatars/reorder/` - изменение порядка

#### 4. Миграции
Создана миграция: `accounts/migrations/0010_useravatar.py`

### Mini App Backend (FastAPI)

**Файл:** `mini_app/routers/api.py`

Добавлены проксирующие эндпоинты:
- POST `/accounts/miniapp-users/{telegram_id}/avatars/`
- DELETE `/accounts/miniapp-users/{telegram_id}/avatars/{avatar_id}/`
- PATCH `/accounts/miniapp-users/{telegram_id}/avatars/reorder/`

### Frontend

#### 1. Стили
**Файл:** `mini_app/static/css/avatar_modal.css` (новый)

- Модальное окно с backdrop
- Swiper для свайпа между аватарками
- Кнопки навигации и закрытия
- Pagination
- Адаптивность для мобильных устройств
- Поддержка GIF badge

#### 2. Шаблоны

**Файл:** `mini_app/templates/user_profile.html`
- Добавлено модальное окно с Swiper для просмотра аватарок чужих профилей

**Файл:** `mini_app/templates/profile.html`
- Добавлено модальное окно с Swiper для просмотра своих аватарок
- Обновлена форма редактирования: поддержка загрузки до 3 файлов

**Файл:** `mini_app/templates/base.html`
- Подключен `avatar_modal.css`

#### 3. JavaScript

**Файл:** `mini_app/static/js/user_profile.js`

Добавлены функции:
- `openAvatarModal(avatars, startIndex)` - открытие модального окна
- `closeAvatarModal()` - закрытие модального окна
- `setupAvatarHandlers(userData)` - настройка обработчиков кликов
- Интеграция с Swiper library

**Файл:** `mini_app/static/js/profile.js`

Аналогичные функции для собственного профиля пользователя.

#### 4. Cache Busting
**Файл:** `mini_app/utils/cache_buster.py`

Обновлены версии:
- `avatar_modal.css` - 1.0
- `profile.js` - 6.0
- `user_profile.js` - 2.0

## Использование

### Просмотр аватарок

1. **На странице "Топ юзерс":**
   - Клик по карточке → открывается модальное окно со свайпером
   - Клик по модальному окну → переход на страницу профиля
   - На странице профиля: клик по аватарке → модальное окно с галереей

2. **На собственной странице профиля:**
   - Клик по аватарке → открывается модальное окно с галереей всех аватарок
   - Свайп влево/вправо для переключения между аватарками
   - Клик вне модального окна или на кнопку × → закрытие

### API использование

#### Загрузка аватарки
```javascript
const formData = new FormData();
formData.append('image', file);
formData.append('order', 0); // опционально

const response = await fetch(`/api/accounts/miniapp-users/${telegram_id}/avatars/`, {
    method: 'POST',
    body: formData
});
```

#### Удаление аватарки
```javascript
const response = await fetch(`/api/accounts/miniapp-users/${telegram_id}/avatars/${avatar_id}/`, {
    method: 'DELETE'
});
```

#### Изменение порядка
```javascript
const response = await fetch(`/api/accounts/miniapp-users/${telegram_id}/avatars/reorder/`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        avatar_orders: [
            { id: 1, order: 0 },
            { id: 2, order: 1 },
            { id: 3, order: 2 }
        ]
    })
});
```

## Технические детали

### Валидация
- Максимум 3 аватарки на пользователя (проверка на уровне модели)
- Поддерживаемые форматы: изображения (jpg, png, etc.) и GIF
- Уникальность порядка (order) для каждого пользователя

### Swiper Configuration
```javascript
{
    slidesPerView: 1,
    spaceBetween: 0,
    centeredSlides: true,
    loop: avatars.length > 1,
    effect: 'slide',
    speed: 300,
    navigation: { nextEl, prevEl },
    pagination: { el, clickable: true }
}
```

### Блокировка скролла
При открытии модального окна:
- `body.overflow = 'hidden'`
- `body.position = 'fixed'`
- Сохранение текущей позиции скролла
- Восстановление при закрытии

## Будущие улучшения

1. **Интеграция загрузки в форму профиля** - полная интеграция загрузки множественных аватарок через форму редактирования профиля
2. **Drag & Drop** - возможность изменения порядка аватарок перетаскиванием
3. **Кропирование** - встроенный редактор для обрезки изображений
4. **Превью в форме** - отображение миниатюр всех аватарок с кнопками удаления
5. **Анимации** - улучшенные переходы и анимации

## Зависимости

- **Swiper.js** - уже подключен в проекте через CDN
- **Django ImageField** - для хранения изображений
- **Pillow** - для обработки изображений (уже установлен)

## Миграция базы данных

```bash
# Миграция уже создана
docker compose run --rm quiz_backend python manage.py migrate accounts
```

## Примечания

- Все комментарии и docstring написаны на русском языке согласно requirements
- API эндпоинты документированы через Swagger (drf-yasg)
- Поддержка Safe Areas для Telegram WebApp
- Адаптивный дизайн для мобильных устройств

