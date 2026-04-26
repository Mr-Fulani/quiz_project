# Спецификация формата источников в JSON при импорте задач

## Цель
Этот документ описывает, как правильно передавать источники (`source`) в JSON-файле для импорта задач.

Логика импорта:
- источник берется только из поля `source` в переводе;
- парсинг источника из `long_explanation` **не используется**;
- если `source` отсутствует, поля источника в БД остаются пустыми.

---

## Где указывать источник
Источник указывается в каждом элементе `translations[]`.

Пример структуры:

```json
{
  "tasks": [
    {
      "topic": "Islam",
      "subtopic": "Namaz",
      "description": "Описание задачи",
      "difficulty": "easy",
      "translations": [
        {
          "language": "ru",
          "question": "Вопрос...",
          "answers": ["A", "B", "C"],
          "correct_answer": "A",
          "explanation": "Короткое объяснение",
          "long_explanation": "Длинное объяснение",
          "source": {
            "text": "Название источника",
            "url": "https://example.com/source"
          }
        }
      ]
    }
  ]
}
```

---

## Поддерживаемые форматы `source`

### 1) Один источник
```json
"source": {
  "text": "Сахих аль-Бухари, Хадис №8",
  "url": "https://sunnah.com/bukhari:8"
}
```

Поля:
- `text` — текст источника (название, описание, ссылка на книгу/хадис и т.д.);
- `url` — ссылка на источник.

Оба поля необязательные, но рекомендуется всегда передавать `text`.

### 2) Несколько источников
```json
"source": {
  "items": [
    {
      "text": "Сахих аль-Бухари, Хадис №8",
      "url": "https://sunnah.com/bukhari:8"
    },
    {
      "text": "Сахих Муслим, Хадис №16",
      "url": "https://sunnah.com/muslim:16"
    }
  ]
}
```

Каждый элемент `items[]` — объект вида `{ "text": "...", "url": "..." }`.

### 3) Только текст без ссылки
```json
"source": {
  "text": "Сахих аль-Бухари, Хадис №8"
}
```

Такой формат корректный: ссылку можно добавить позже вручную в админке.

### 4) Источник отсутствует
Если источника нет:
- не передавайте поле `source`, или
- передайте пустой объект:

```json
"source": {}
```

В этом случае поля источника в БД останутся пустыми.

---

## Важные правила для контент-команды
- Не используйте строки вида `Источник: ...` внутри `long_explanation` как источник данных для импорта.
- Если нужно передать несколько источников, используйте только `source.items`.
- Формат одинаковый для всех языков (`ru`, `en` и т.д.).
- Пустые строки в `text` и `url` считаются отсутствием значения.

---

## Пример RU + EN с двумя источниками

```json
{
  "tasks": [
    {
      "topic": "Islam",
      "subtopic": "Namaz",
      "description": "Intermediate knowledge about prayer conditions and validity.",
      "difficulty": "medium",
      "translations": [
        {
          "language": "ru",
          "question": "Что нарушает намаз по мнению большинства ученых?",
          "answers": ["Преднамеренная речь", "Моргание", "Дыхание"],
          "correct_answer": "Преднамеренная речь",
          "explanation": "Намеренная речь нарушает намаз.",
          "long_explanation": "По мнению большинства исламских ученых, преднамеренная речь во время намаза нарушает его.",
          "source": {
            "items": [
              {
                "text": "Сахих аль-Бухари, Хадис №8",
                "url": "https://sunnah.com/bukhari:8"
              },
              {
                "text": "Сахих Муслим, Хадис №16",
                "url": "https://sunnah.com/muslim:16"
              }
            ]
          }
        },
        {
          "language": "en",
          "question": "What invalidates Salah according to the majority of scholars?",
          "answers": ["Intentional speech", "Blinking", "Breathing"],
          "correct_answer": "Intentional speech",
          "explanation": "Intentional speech invalidates prayer.",
          "long_explanation": "According to the majority of scholars, intentional speech during Salah invalidates the prayer.",
          "source": {
            "items": [
              {
                "text": "Sahih al-Bukhari, Hadith #8",
                "url": "https://sunnah.com/bukhari:8"
              },
              {
                "text": "Sahih Muslim, Hadith #16",
                "url": "https://sunnah.com/muslim:16"
              }
            ]
          }
        }
      ]
    }
  ]
}
```
