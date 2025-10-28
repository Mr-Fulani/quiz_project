"""
Management команда для импорта текущих данных резюме из шаблона в БД.
Используйте: python manage.py import_resume
"""
from django.core.management.base import BaseCommand
from blog.models import Resume


class Command(BaseCommand):
    help = 'Импортирует данные резюме из шаблона в БД'

    def handle(self, *args, **kwargs):
        """Создает резюме с текущими данными"""
        
        # Проверяем, есть ли уже активное резюме
        existing = Resume.objects.filter(is_active=True).first()
        if existing:
            self.stdout.write(
                self.style.WARNING(f'Активное резюме уже существует (ID: {existing.id})')
            )
            confirm = input('Хотите перезаписать его? (yes/no): ')
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.ERROR('Импорт отменён'))
                return
            existing.delete()
        
        # Данные резюме из текущего шаблона
        resume_data = {
            'name': 'Anvar Sharipov',
            'contact_info_en': 'Istanbul, Turkey 34520 | +905525821497',
            'contact_info_ru': 'Стамбул, Турция 34520 | +905525821497',
            'email': 'fulani.dev@gmail.com',
            'websites': [
                'https://github.com/Mr-Fulani',
                'https://t.me/Mr_Fulani'
            ],
            'summary_en': 'Organized and dependable candidate successful at managing multiple priorities with a positive attitude. Willingness to take on added responsibilities to meet team goals.',
            'summary_ru': 'Организованный и надёжный кандидат, успешно справляющийся с несколькими задачами с позитивным настроем. Готов брать на себя дополнительные обязанности для достижения командных целей.',
            'skills': [
                'Linux Environments',
                'Python',
                'Django (DRF)',
                'FastAPI',
                'Flask',
                'Docker',
                'API Development',
                'SQLAlchemy'
            ],
            'work_history': [
                {
                    'title_en': 'Private Practice / Freelancing Remote',
                    'title_ru': 'Частная практика / Фриланс удалённо',
                    'period_en': '01/2023 to Current',
                    'period_ru': '01/2023 по настоящее время',
                    'company_en': 'Upwork.com',
                    'company_ru': 'Upwork.com',
                    'responsibilities_en': [
                        'Self-motivated, with a strong sense of personal responsibility.',
                        'Skilled at working independently and collaboratively in a team environment.'
                    ],
                    'responsibilities_ru': [
                        'Самомотивирован, с сильным чувством личной ответственности.',
                        'Умение работать самостоятельно и в команде.'
                    ]
                },
                {
                    'title_en': 'Middle Software Developer',
                    'title_ru': 'Средний разработчик программного обеспечения',
                    'period_en': '01/2023 to 08/2024',
                    'period_ru': '01/2023 по 08/2024',
                    'company_en': 'AS TRANSFER DIJTAL IÇERIK TEKNOLOJILERI LiMiTED, Istanbul, Turkey',
                    'company_ru': 'AS TRANSFER DIJTAL IÇERIK TEKNOLOJILERI LiMiTED, Стамбул, Турция',
                    'responsibilities_en': [
                        'Improved software efficiency by troubleshooting and resolving coding issues.',
                        'Saved time and resources by identifying and fixing bugs before product deployment.',
                        'Discussed issues with team members to provide resolution and apply best practices.',
                        'Updated old code bases to modern development standards, improving functionality.',
                        'Optimized application performance by conducting regular code reviews and refactoring when necessary.',
                        'Estimated work hours and tracked progress using Scrum methodology.',
                        'Built databases and table structures for web applications.'
                    ],
                    'responsibilities_ru': [
                        'Улучшил эффективность ПО, устраняя проблемы в коде.',
                        'Сэкономил время и ресурсы, исправляя ошибки перед запуском продукта.',
                        'Обсуждал проблемы с членами команды для их решения и применения лучших практик.',
                        'Обновлял старые кодовые базы до современных стандартов разработки, улучшая функциональность.',
                        'Оптимизировал производительность приложений, проводя регулярные проверки кода и рефакторинг при необходимости.',
                        'Оценивал рабочее время и отслеживал прогресс с использованием методологии Scrum.',
                        'Создавал базы данных и структуры таблиц для веб-приложений.'
                    ]
                },
                {
                    'title_en': 'Junior Software Developer',
                    'title_ru': 'Младший разработчик программного обеспечения',
                    'period_en': '07/2022 to 01/2023',
                    'period_ru': '07/2022 по 01/2023',
                    'company_en': 'AS TRANSFER DIJTAL IÇERIK TEKNOLOJILERI LiMiTED Si, Istanbul, Turkey',
                    'company_ru': 'AS TRANSFER DIJTAL IÇERIK TEKNOLOJILERI LiMiTED Si, Стамбул, Турция',
                    'responsibilities_en': [
                        'Contributed to the successful launch of a new software product by assisting with the design, development, and implementation phases.',
                        'Discussed issues with team members to provide resolution and apply best practices.',
                        'Built databases and table structures for web applications.'
                    ],
                    'responsibilities_ru': [
                        'Способствовал успешному запуску нового программного продукта, помогая в фазах проектирования, разработки и внедрения.',
                        'Обсуждал проблемы с членами команды для их решения и применения лучших практик.',
                        'Создавал базы данных и структуры таблиц для веб-приложений.'
                    ]
                }
            ],
            'education': [
                {
                    'title_en': 'Master of Arts: Information Systems And Technologies, Development',
                    'title_ru': 'Магистр искусств: Информационные системы и технологии, разработка',
                    'period_en': '05/2010',
                    'period_ru': '05/2010',
                    'institution_en': 'National R. University of Information Technologies, St. Petersburg, Russia',
                    'institution_ru': 'Национальный университет информационных технологий, Санкт-Петербург, Россия'
                }
            ],
            'languages': [
                {'name_en': 'Russian: Native', 'name_ru': 'Русский: Родной', 'level': 100},
                {'name_en': 'English: Intermediate (B1)', 'name_ru': 'Английский: Средний (B1)', 'level': 60},
                {'name_en': 'Persian: Native', 'name_ru': 'Персидский: Родной', 'level': 80},
                {'name_en': 'Turkish: (B2)', 'name_ru': 'Турецкий: (B2)', 'level': 80}
            ],
            'is_active': True
        }
        
        # Создаем резюме
        resume = Resume.objects.create(**resume_data)
        
        self.stdout.write(
            self.style.SUCCESS(f'✓ Резюме успешно импортировано (ID: {resume.id})')
        )
        self.stdout.write(self.style.SUCCESS(f'  Имя: {resume.name}'))
        self.stdout.write(self.style.SUCCESS(f'  Email: {resume.email}'))
        self.stdout.write(self.style.SUCCESS(f'  Навыков: {len(resume.skills)}'))
        self.stdout.write(self.style.SUCCESS(f'  Записей в Work History: {len(resume.work_history)}'))
        self.stdout.write(self.style.SUCCESS(f'  Записей в Education: {len(resume.education)}'))
        self.stdout.write(self.style.SUCCESS(f'  Языков: {len(resume.languages)}'))

