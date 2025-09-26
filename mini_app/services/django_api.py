import httpx
import logging

from core.config import settings

logger = logging.getLogger(__name__)

# Fallback данные для подтем
def get_fallback_subtopics(topic_id: int):
    """
    Резервные данные подтем на случай недоступности Django API
    """
    fallback_data = {
        8: [  # Python
            {"id": 1, "name": "Синтаксис", "questions_count": 8},
            {"id": 2, "name": "Структуры данных", "questions_count": 6},
            {"id": 3, "name": "ООП", "questions_count": 7},
            {"id": 4, "name": "Библиотеки", "questions_count": 5}
        ],
        9: [  # JavaScript
            {"id": 5, "name": "DOM", "questions_count": 5},
            {"id": 6, "name": "Async/Await", "questions_count": 4},
            {"id": 7, "name": "ES6+", "questions_count": 6},
            {"id": 8, "name": "Frameworks", "questions_count": 5}
        ],
        10: [  # React
            {"id": 9, "name": "Компоненты", "questions_count": 8},
            {"id": 10, "name": "Hooks", "questions_count": 7},
            {"id": 11, "name": "State Management", "questions_count": 6},
            {"id": 12, "name": "Router", "questions_count": 4}
        ],
        11: [  # SQL
            {"id": 13, "name": "SELECT запросы", "questions_count": 6},
            {"id": 14, "name": "JOIN операции", "questions_count": 5},
            {"id": 15, "name": "Индексы", "questions_count": 4},
            {"id": 16, "name": "Процедуры", "questions_count": 3}
        ],
        13: [  # Django
            {"id": 17, "name": "Модели и ORM", "questions_count": 6},
            {"id": 18, "name": "Views и URLs", "questions_count": 5},
            {"id": 19, "name": "Templates", "questions_count": 4},
            {"id": 20, "name": "Forms", "questions_count": 5}
        ],
        14: [  # Docker
            {"id": 21, "name": "Контейнеры", "questions_count": 7},
            {"id": 22, "name": "Docker Compose", "questions_count": 6},
            {"id": 23, "name": "Volumes", "questions_count": 4},
            {"id": 24, "name": "Networks", "questions_count": 3}
        ],
        15: [  # Git
            {"id": 25, "name": "Основные команды", "questions_count": 8},
            {"id": 26, "name": "Ветки", "questions_count": 5},
            {"id": 27, "name": "Merge и Rebase", "questions_count": 4},
            {"id": 28, "name": "Remote репозитории", "questions_count": 3}
        ],
        16: [  # Golang
            {"id": 29, "name": "Goroutines", "questions_count": 7},
            {"id": 30, "name": "Channels", "questions_count": 5},
            {"id": 31, "name": "Interfaces", "questions_count": 6},
            {"id": 32, "name": "Packages", "questions_count": 4}
        ]
    }
    
    logger.info(f"Getting fallback subtopics for topic_id: {topic_id}")
    result = fallback_data.get(topic_id, [])
    logger.info(f"Returning {len(result)} subtopics for topic {topic_id}")
    return result

# Fallback данные на случай недоступности Django API
def get_fallback_topics():
    """
    Резервные статические данные тем на случай недоступности Django API
    """
    return [
        {
            "id": 1,
            "name": "Python",
            "description": "Тестирование знаний Python",
            "image_url": "https://picsum.photos/400/400?1",
            "difficulty": "Средний",
            "questions_count": 25
        },
        {
            "id": 2,
            "name": "JavaScript", 
            "description": "Основы JavaScript",
            "image_url": "https://picsum.photos/400/400?2",
            "difficulty": "Легкий",
            "questions_count": 20
        },
        {
            "id": 3,
            "name": "React",
            "description": "React фреймворк",
            "image_url": "https://picsum.photos/400/400?3", 
            "difficulty": "Сложный",
            "questions_count": 30
        },
        {
            "id": 4,
            "name": "SQL",
            "description": "Базы данных SQL",
            "image_url": "https://picsum.photos/400/400?4",
            "difficulty": "Средний", 
            "questions_count": 22
        }
    ]

class DjangoAPIService:
    def __init__(self):
        self.base_url = settings.DJANGO_API_BASE_URL
        self.headers = {
            "Authorization": f"Token {settings.DJANGO_API_TOKEN}",
            "Content-Type": "application/json"
        }

    async def get_user_profile(self, telegram_id: int):
        profile_url = f"{self.base_url}/api/accounts/profile/by-telegram/{telegram_id}/"
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await client.get(profile_url, headers=self.headers)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Ошибка получения профиля ({e.response.status_code}) для telegram_id={telegram_id}: {e.response.text}")
            return None
        except Exception as e:
            logger.exception(f"Неожиданная ошибка при запросе к Django API для telegram_id={telegram_id}")
            return None 