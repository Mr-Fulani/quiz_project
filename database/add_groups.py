import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from database.database import AsyncSessionMaker as async_session_maker
from database.models import Topic, Group



# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)




async def create_groups(db_session: AsyncSession):
    # Полный список данных для групп и каналов
    locations = [
        # Группы
        # {'group_name': 'PYTHONCHIK', 'group_id': -1002402788132, 'topic_name': 'Python', 'language': 'ru'},
        # {'group_name': 'PYTHONCHIK QUIZ', 'group_id': -1002214492683, 'topic_name': 'Python', 'language': 'en'},
        # {'group_name': 'PYTHONCHIK TR', 'group_id': -1002351236697, 'topic_name': 'Python', 'language': 'tr'},
        #
        # # Golang группы
        # {'group_name': 'Golang Rus', 'group_id': -1002303816057, 'topic_name': 'Golang', 'language': 'ru'},
        # {'group_name': 'Golang Eng', 'group_id': -1002324902451, 'topic_name': 'Golang', 'language': 'en'},
        # {'group_name': 'Golang Tur', 'group_id': -1002442206312, 'topic_name': 'Golang', 'language': 'tr'},
        #
        # # SQL группы
        # {'group_name': 'SQL Hub Rus', 'group_id': -1002497642955, 'topic_name': 'SQL', 'language': 'ru'},
        # {'group_name': 'SQL Hub Eng', 'group_id': -1002271292246, 'topic_name': 'SQL', 'language': 'en'},
        # {'group_name': 'SQL Hub Tur', 'group_id': -1002360744463, 'topic_name': 'SQL', 'language': 'tr'},
        #
        # # Django группы
        # {'group_name': 'Django Hub', 'group_id': -1002282339315, 'topic_name': 'Django', 'language': 'ru'},
        # {'group_name': 'Django Hub', 'group_id': -1002265688702, 'topic_name': 'Django', 'language': 'en'},
        # {'group_name': 'Django Hub', 'group_id': -1002468028379, 'topic_name': 'Django', 'language': 'tr'},

        # Каналы
        {'group_name': 'Golang Channel', 'group_id': -1002301205149, 'topic_name': 'Golang', 'language': 'en',
         'location_type': 'channel'},
        {'group_name': 'Django Hub Channel', 'group_id': -1002351518503, 'topic_name': 'Django', 'language': 'en',
         'location_type': 'channel'},
        {'group_name': 'Pythonist Channel', 'group_id': -1002393359575, 'topic_name': 'Python', 'language': 'en',
         'location_type': 'channel'},
        {'group_name': 'SQL HUB Channel', 'group_id': -1002469822792, 'topic_name': 'SQL', 'language': 'en',
         'location_type': 'channel'},
        {'group_name': 'PYTHON TURKIYE Channel', 'group_id': -1002116101730, 'topic_name': 'Python', 'language': 'tr',
         'location_type': 'channel'},
    ]

    logger.info("Начало обработки добавления групп и каналов.")


    for location_data in locations:
        try:
            # Логируем данные, которые добавляем
            logger.info(f"Обработка: {location_data}")

            # Поиск топика по названию
            result = await db_session.execute(select(Topic).where(Topic.name == location_data["topic_name"]))
            topic = result.scalar_one_or_none()

            if not topic:
                logger.error(f"Тема '{location_data['topic_name']}' не найдена. Пропуск.")
                continue
            logger.info(f"Тема '{location_data['topic_name']}' найдена, ID: {topic.id}")

            # Проверка существования группы или канала с таким же ID
            result = await db_session.execute(
                select(Group).where(Group.group_id == location_data["group_id"])
            )
            existing_group = result.scalar_one_or_none()

            if existing_group:
                logger.info(
                    f"Локация '{location_data['group_name']}' с ID {location_data['group_id']} уже существует. Пропуск.")
                continue

            # Добавляем новую группу или канал
            new_group = Group(
                group_name=location_data["group_name"],
                group_id=location_data["group_id"],
                topic_id=topic.id,
                language=location_data["language"],
                location_type=location_data.get("location_type", "group")  # По умолчанию "group"
            )
            db_session.add(new_group)
            logger.info(f"Локация '{location_data['group_name']}' успешно добавлена.")

        except Exception as e:
            logger.error(f"Ошибка при обработке '{location_data['group_name']}': {e}")

    # Сохранение изменений в базе
    try:
        await db_session.commit()
        logger.info("Все изменения сохранены в базе данных.")
    except Exception as e:
        logger.error(f"Ошибка при сохранении данных: {e}")
        await db_session.rollback()

    logger.info("Обработка групп и каналов завершена.")



async def main():
    async with async_session_maker() as session:
        await create_groups(session)




if __name__ == "__main__":
    asyncio.run(main())