"""
Management команда для миграции данных резюме из JSON полей в новые модели.
Используйте: python manage.py migrate_resume_to_models
"""
from django.core.management.base import BaseCommand
from blog.models import (
    Resume, ResumeWebsite, ResumeSkill, ResumeWorkHistory, 
    ResumeResponsibility, ResumeEducation, ResumeLanguage
)


class Command(BaseCommand):
    help = 'Мигрирует данные резюме из JSON полей в новые модели'

    def handle(self, *args, **kwargs):
        """Переносит данные из JSON в связанные модели"""
        
        resumes = Resume.objects.all()
        
        if not resumes.exists():
            self.stdout.write(self.style.WARNING('Резюме не найдено в БД'))
            return
        
        for resume in resumes:
            self.stdout.write(f'\n📄 Обрабатываем резюме: {resume.name}')
            
            # Миграция веб-сайтов
            if resume.websites:
                self.stdout.write('  Мигрируем веб-сайты...')
                for order, url in enumerate(resume.websites):
                    ResumeWebsite.objects.get_or_create(
                        resume=resume,
                        url=url,
                        defaults={'order': order}
                    )
                self.stdout.write(self.style.SUCCESS(f'    ✓ Создано {len(resume.websites)} веб-сайтов'))
            
            # Миграция навыков
            if resume.skills:
                self.stdout.write('  Мигрируем навыки...')
                for order, skill_name in enumerate(resume.skills):
                    ResumeSkill.objects.get_or_create(
                        resume=resume,
                        name=skill_name,
                        defaults={'order': order}
                    )
                self.stdout.write(self.style.SUCCESS(f'    ✓ Создано {len(resume.skills)} навыков'))
            
            # Миграция истории работы
            if resume.work_history:
                self.stdout.write('  Мигрируем историю работы...')
                for order, work in enumerate(resume.work_history):
                    work_history_obj, created = ResumeWorkHistory.objects.get_or_create(
                        resume=resume,
                        title_en=work.get('title_en', ''),
                        title_ru=work.get('title_ru', ''),
                        defaults={
                            'period_en': work.get('period_en', ''),
                            'period_ru': work.get('period_ru', ''),
                            'company_en': work.get('company_en', ''),
                            'company_ru': work.get('company_ru', ''),
                            'order': order
                        }
                    )
                    
                    # Миграция обязанностей для этой записи
                    responsibilities_en = work.get('responsibilities_en', [])
                    responsibilities_ru = work.get('responsibilities_ru', [])
                    
                    # Берём максимальную длину из двух списков
                    max_len = max(len(responsibilities_en), len(responsibilities_ru))
                    
                    for resp_order in range(max_len):
                        text_en = responsibilities_en[resp_order] if resp_order < len(responsibilities_en) else ''
                        text_ru = responsibilities_ru[resp_order] if resp_order < len(responsibilities_ru) else ''
                        
                        if text_en or text_ru:
                            ResumeResponsibility.objects.get_or_create(
                                work_history=work_history_obj,
                                text_en=text_en,
                                text_ru=text_ru,
                                defaults={'order': resp_order}
                            )
                
                self.stdout.write(self.style.SUCCESS(f'    ✓ Создано {len(resume.work_history)} записей истории работы'))
            
            # Миграция образования
            if resume.education:
                self.stdout.write('  Мигрируем образование...')
                for order, edu in enumerate(resume.education):
                    ResumeEducation.objects.get_or_create(
                        resume=resume,
                        title_en=edu.get('title_en', ''),
                        title_ru=edu.get('title_ru', ''),
                        defaults={
                            'period_en': edu.get('period_en', ''),
                            'period_ru': edu.get('period_ru', ''),
                            'institution_en': edu.get('institution_en', ''),
                            'institution_ru': edu.get('institution_ru', ''),
                            'order': order
                        }
                    )
                self.stdout.write(self.style.SUCCESS(f'    ✓ Создано {len(resume.education)} записей об образовании'))
            
            # Миграция языков
            if resume.languages:
                self.stdout.write('  Мигрируем языки...')
                for order, lang in enumerate(resume.languages):
                    ResumeLanguage.objects.get_or_create(
                        resume=resume,
                        name_en=lang.get('name_en', ''),
                        name_ru=lang.get('name_ru', ''),
                        defaults={
                            'level': lang.get('level', 50),
                            'order': order
                        }
                    )
                self.stdout.write(self.style.SUCCESS(f'    ✓ Создано {len(resume.languages)} языков'))
        
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('✅ Миграция завершена успешно!'))
        self.stdout.write(self.style.SUCCESS('\nТеперь вы можете редактировать резюме через удобные формы в админке.'))
        self.stdout.write(self.style.SUCCESS('JSON поля можно оставить для обратной совместимости или очистить.'))

