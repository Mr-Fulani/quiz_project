# Настройка Pinterest API

## Шаг 1: Получение данных из Pinterest

Вы уже получили:
- **Access Token (trial)**: `pina_AMAZU6IXADZ5WAYAGCAH6DAAJKLNLGQBQBIQDT6C3WMU3G4G3Q3Z7MMRPAJLMBDYIV5KKH6R7UBSDF2EM675BNAGP45OKFAA`
- **App ID**: `1538458`

⚠️ **Важно**: 
- Trial токен действует только 24 часа
- **Trial уровень доступа позволяет создавать пины**, но они будут видны только вам (приватные)
- **Статус "Доступ к Trial на рассмотрении"** означает, что приложение еще не одобрено
- Пока приложение не одобрено, вы получите ошибку: "Your application consumer type is not supported"
- После одобрения Trial доступа можно будет создавать приватные пины
- Для публичных пинов нужен Standard/Basic уровень доступа через OAuth

---

## Шаг 2: Получение Board ID

⚠️ **Trial токен не поддерживает API endpoints**, поэтому получаем board_id вручную:

### Способ 1: Из URL доски (самый простой)

1. Откройте Pinterest в браузере
2. Перейдите на вашу доску (или создайте новую)
3. Скопируйте URL доски, например:
   - `https://pinterest.com/your-username/quiz-tasks/`
   - `https://pinterest.com/your-username/programming-quiz/`

4. **Board ID** будет: `your-username/quiz-tasks` или `your-username/programming-quiz`

### Способ 2: Создать новую доску

1. Зайдите в Pinterest
2. Создайте новую доску (например, "Quiz Tasks" или "Programming Quiz")
3. Скопируйте URL доски
4. Извлеките board_id из URL

### Формат Board ID

Pinterest использует формат: `username/board-name`

Примеры:
- `mrproger/quiz-tasks`
- `myusername/programming-quiz`
- `user123/python-coding`

---

## Шаг 3: Настройка в Django админке

1. Откройте Django админку: `http://localhost:8001/admin/`

2. Перейдите: **Webhooks → Social Media Credentials**

3. Нажмите **"Добавить Social Media Credentials"**

4. Заполните форму:
   - **Platform**: `Pinterest`
   - **Access Token**: `pina_AMAZU6IXADZ5WAYAGCAH6DAAJKLNLGQBQBIQDT6C3WMU3G4G3Q3Z7MMRPAJLMBDYIV5KKH6R7UBSDF2EM675BNAGP45OKFAA`
   - **Refresh Token**: (оставьте пустым для trial токена)
   - **Token Expires At**: `2025-12-01 19:26:27` (через 24 часа от момента создания)
   - **Extra Data**: 
     ```json
     {
       "board_id": "your-username/your-board-name"
     }
     ```
     Или числовой ID:
     ```json
     {
       "board_id": "123456789"
     }
     ```
   - **Is Active**: ⚠️ **Отключите** (если используете trial токен - он не работает)
     - Для trial токена: ❌ **Is Active: выключено** (чтобы не получать ошибки)
     - Для production токена: ✅ **Is Active: включено**

5. Нажмите **"Сохранить"**

**Примечание:** Если у вас только trial токен, лучше **отключить** Pinterest в credentials (`Is Active: False`), чтобы система не пыталась публиковать и не засоряла логи ошибками. Включите его только когда получите постоянный токен.

---

## Шаг 4: Тестирование

1. Создайте задачу в админке с изображением
2. Установите `published=True`
3. Проверьте логи:
   ```bash
   docker compose logs -f quiz_backend | grep -i pinterest
   ```
4. Проверьте Pinterest - пин должен появиться на доске
5. В админке → **Tasks → Social Media Posts** проверьте статус публикации

---

## Для чего нужен Trial токен?

Trial уровень доступа от Pinterest позволяет:

✅ **Что можно делать (после одобрения):**
- Создавать стандартные пины (`pins:write`) - **но они будут приватными** (видны только вам)
- Читать доски (`boards:read`)
- Читать пины (`pins:read`)
- Базовую аналитику
- Читать рекламу

⚠️ **Ограничения Trial:**
- Пины видны только создателю (не публичные)
- Лимит: 1000 запросов в день
- Токен действует 24 часа

**Статус "Доступ к Trial на рассмотрении":**
- Pinterest рассматривает вашу заявку
- Пока не одобрено - API не работает (ошибка "consumer type is not supported")
- После одобрения можно создавать приватные пины для тестирования

**Для публичных пинов** нужен **Standard** или **Basic** уровень доступа через OAuth.

---

## Получение постоянного токена (для production)

Trial токен действует только 24 часа и не поддерживает создание пинов. Для production нужен постоянный токен:

### OAuth 2.0 Flow

1. **Настройте Redirect URI** в Pinterest:
   - В настройках приложения добавьте: `https://your-domain.com/auth/pinterest/callback/`

2. **Создайте OAuth endpoint** в Django (опционально, можно сделать позже):
   ```python
   # Пример URL для авторизации
   https://www.pinterest.com/oauth/?client_id=1538458&redirect_uri=https://your-domain.com/auth/pinterest/callback/&response_type=code&scope=boards:read,pins:write
   ```

3. **Получите authorization code** и обменяйте на access token

4. **Access token** можно обновлять через refresh token

---

## Текущие разрешения (Scopes)

Ваш trial токен имеет доступ к:
- ✅ `pins:read` - чтение пинов
- ✅ `boards:read` - чтение досок
- ✅ `user_accounts:read` - чтение аккаунта
- ✅ `ads:read` - чтение рекламы
- ✅ `catalogs:read` - чтение каталогов

Для создания пинов нужен `pins:write` - запросите его при получении постоянного токена.

---

## Проверка токена через API

⚠️ **Trial токен не поддерживает большинство API endpoints**. Ошибка: "Your application consumer type is not supported"

Для проверки токена нужно:
1. Настроить credentials в Django админке
2. Создать тестовую задачу с `published=True`
3. Проверить логи и статус публикации в админке

Если публикация пройдёт успешно - токен работает!

---

## Troubleshooting

### Ошибка: "Your application consumer type is not supported"
- **Причина:** Приложение еще не одобрено для Trial доступа (статус "Доступ к Trial на рассмотрении")
- **Решение:** 
  1. Дождитесь одобрения Trial доступа от Pinterest (обычно 1-3 дня)
  2. После одобрения trial токен сможет создавать приватные пины
  3. Или временно отключите Pinterest (`Is Active: False`) до одобрения
  4. Для публичных пинов нужен Standard/Basic уровень через OAuth

### Ошибка: "Invalid access token"
- Проверьте, что токен скопирован полностью
- Убедитесь, что токен не истёк (24 часа для trial)

### Ошибка: "Board not found"
- Проверьте board_id в extra_data
- Убедитесь, что доска существует и доступна

### Ошибка: "Insufficient permissions"
- Trial токен не имеет права `pins:write`
- Для создания пинов нужен постоянный токен через OAuth с правильными scopes

---

## Следующие шаги

### Если Trial доступ еще на рассмотрении:
1. ✅ Настройте credentials в админке (сохраните токен)
2. ⚠️ **Отключите Pinterest** (`Is Active: False`) - пока не одобрено
3. ⏳ Дождитесь одобрения Trial доступа от Pinterest (1-3 дня)
4. ✅ После одобрения включите Pinterest и протестируйте создание приватных пинов

### Если Trial доступ уже одобрен:
1. ✅ Настройте credentials в админке
2. ✅ Получите board_id
3. ✅ Включите Pinterest (`Is Active: True`)
4. ✅ Протестируйте публикацию (пины будут приватными, видны только вам)

### Для публичных пинов (Production):
1. ⏳ Получите Standard/Basic уровень доступа через OAuth
2. ✅ Настройте постоянный токен в credentials
3. ✅ Протестируйте публикацию публичных пинов

