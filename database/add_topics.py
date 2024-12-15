# database/add_topics.py

import asyncio
import logging
import sys

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import SQLAlchemyError

# Убедитесь, что пути импорта корректны в вашем проекте
from database.database import AsyncSessionMaker as async_session_maker
from database.models import Topic

# Настройка логгера
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


async def create_topics(db_session: AsyncSession):
    topics = [
        # Языки программирования
        'Python', 'Golang', 'Java', 'C', 'C++', 'C#', 'JavaScript', 'TypeScript',
        'Ruby', 'Kotlin', 'Swift', 'PHP', 'R', 'Perl', 'Rust', 'Scala', 'Haskell',
        'Objective-C', 'Dart', 'Elixir', 'F#', 'Lua', 'MATLAB', 'Shell', 'Assembly',

        # Фреймворки и библиотеки
        'Django', 'Flask', 'FastAPI', 'Spring', 'React', 'Vue.js', 'Angular',
        'Express.js', 'Next.js', 'Nuxt.js', 'Svelte', 'Laravel', 'Symfony',
        'Ruby on Rails', 'ASP.NET', 'Bootstrap', 'TailwindCSS', 'TensorFlow',
        'PyTorch', 'Keras', 'Scikit-learn', 'Pandas', 'NumPy', 'Matplotlib',

        # Базы данных
        'SQL', 'PostgreSQL', 'MySQL', 'SQLite', 'MongoDB', 'Redis', 'Cassandra',
        'DynamoDB', 'Firebase', 'Elasticsearch', 'Neo4j', 'MariaDB', 'Oracle Database',

        # DevOps и инфраструктура
        'Docker', 'Kubernetes', 'Ansible', 'Terraform', 'AWS', 'Azure', 'Google Cloud',
        'Jenkins', 'GitLab CI/CD', 'CircleCI', 'Travis CI', 'Prometheus', 'Grafana',
        'Consul', 'HashiCorp Vault', 'OpenShift', 'Vagrant',

        # Технологии и инструменты
        'Blockchain', 'Ethereum', 'Solidity', 'Hyperledger', 'React Native',
        'Flutter', 'Ionic', 'Unity', 'Unreal Engine', 'Qt', 'Electron', 'WebAssembly',
        'gRPC', 'REST APIs', 'GraphQL', 'WebRTC', 'Microservices', 'Monoliths',
        'Serverless', 'Edge Computing',

        # Разработка игр
        'Game Development', 'Godot', 'Unreal Engine', 'CryEngine', 'Construct',
        'Blender', 'OpenGL', 'DirectX', 'Vulkan',

        # Искусственный интеллект и машинное обучение
        'Machine Learning', 'Deep Learning', 'Natural Language Processing',
        'Computer Vision', 'Reinforcement Learning', 'Chatbots', 'AI Ethics',
        'Explainable AI',

        # Анализ данных и наука о данных
        'Data Science', 'Big Data', 'Data Visualization', 'Data Engineering',
        'Business Intelligence', 'Apache Spark', 'Hadoop', 'Tableau', 'Power BI',

        # Кибербезопасность
        'Cybersecurity', 'Penetration Testing', 'Ethical Hacking', 'Cryptography',
        'Network Security', 'SIEM', 'OWASP', 'Nmap', 'Metasploit', 'Burp Suite',

        # Инструменты разработки
        'Git', 'GitHub', 'GitLab', 'Bitbucket', 'VS Code', 'IntelliJ IDEA',
        'PyCharm', 'WebStorm', 'Eclipse', 'NetBeans', 'Atom', 'Sublime Text',

        # Теоретические темы
        'Algorithms', 'Data Structures', 'Operating Systems', 'Computer Networks',
        'Compiler Design', 'Theory of Computation', 'Parallel Computing',
        'Quantum Computing',

        # Мобильная разработка
        'Android', 'iOS', 'React Native', 'Flutter', 'SwiftUI', 'Jetpack Compose',

        # Другие полезные темы
        'Agile Methodologies', 'Scrum', 'Kanban', 'Lean Development', 'Design Patterns',
        'Clean Code', 'Refactoring', 'Code Review', 'Technical Debt', 'Testing',
        'Unit Testing', 'Integration Testing', 'Load Testing', 'API Testing',
        'UI/UX Design', 'Human-Computer Interaction', 'Accessibility'
    ]

    logger.info("Начало добавления тем.")

    for topic_name in topics:
        try:
            # Проверка существования темы
            result = await db_session.execute(select(Topic).where(Topic.name.ilike(topic_name)))
            topic = result.scalar_one_or_none()

            if topic:
                logger.info(f"Тема '{topic_name}' уже существует. Пропуск.")
                continue

            # Добавление новой темы
            new_topic = Topic(name=topic_name)
            db_session.add(new_topic)
            logger.info(f"Тема '{topic_name}' успешно добавлена.")
        except SQLAlchemyError as e:
            logger.error(f"Ошибка при добавлении темы '{topic_name}': {e}")
            await db_session.rollback()
        except Exception as e:
            logger.error(f"Непредвиденная ошибка при добавлении темы '{topic_name}': {e}")
            await db_session.rollback()

    # Сохранение изменений
    try:
        await db_session.commit()
        logger.info("Все темы успешно сохранены в базе данных.")
    except SQLAlchemyError as e:
        logger.error(f"Ошибка при сохранении тем: {e}")
        await db_session.rollback()
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при сохранении тем: {e}")
        await db_session.rollback()


async def main():
    async with async_session_maker() as session:
        await create_topics(session)


if __name__ == "__main__":
    asyncio.run(main())


