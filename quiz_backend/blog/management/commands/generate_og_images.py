from django.core.management.base import BaseCommand
from blog.models import Post, Project


class Command(BaseCommand):
    help = 'Генерирует Open Graph картинки для всех постов и проектов'

    def add_arguments(self, parser):
        parser.add_argument(
            '--posts-only',
            action='store_true',
            help='Генерировать только для постов',
        )
        parser.add_argument(
            '--projects-only',
            action='store_true',
            help='Генерировать только для проектов',
        )

    def handle(self, *args, **options):
        posts_only = options['posts_only']
        projects_only = options['projects_only']

        if not projects_only:
            self.stdout.write('🖼️  Генерирую OG картинки для постов...')
            posts = Post.objects.filter(published=True)
            
            for post in posts:
                try:
                    og_url = post.get_og_image_url()
                    if og_url:
                        if post.get_main_image():
                            self.stdout.write(
                                self.style.SUCCESS(f'✅ Пост "{post.title}": {og_url} 📷 СУЩЕСТВУЮЩАЯ КАРТИНКА')
                            )
                        else:
                            self.stdout.write(
                                self.style.SUCCESS(f'✅ Пост "{post.title}": {og_url} 🖼️ СГЕНЕРИРОВАННАЯ OG КАРТИНКА')
                            )
                    else:
                        self.stdout.write(
                            self.style.ERROR(f'❌ Ошибка для поста "{post.title}"')
                        )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'❌ Ошибка для поста "{post.title}": {e}')
                    )

        if not posts_only:
            self.stdout.write('🖼️  Генерирую OG картинки для проектов...')
            projects = Project.objects.all()
            
            for project in projects:
                try:
                    og_url = project.get_og_image_url()
                    if og_url:
                        if project.get_main_image():
                            self.stdout.write(
                                self.style.SUCCESS(f'✅ Проект "{project.title}": {og_url} 📷 СУЩЕСТВУЮЩАЯ КАРТИНКА')
                            )
                        else:
                            self.stdout.write(
                                self.style.SUCCESS(f'✅ Проект "{project.title}": {og_url} 🖼️ СГЕНЕРИРОВАННАЯ OG КАРТИНКА')
                            )
                    else:
                        self.stdout.write(
                            self.style.ERROR(f'❌ Ошибка для проекта "{project.title}"')
                        )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'❌ Ошибка для проекта "{project.title}": {e}')
                    )

        self.stdout.write(
            self.style.SUCCESS('🎉 Генерация OG картинок завершена!')
        ) 