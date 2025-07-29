from django.core.management.base import BaseCommand
from blog.models import Post, Project, PostImage, ProjectImage
from django.db import transaction


class Command(BaseCommand):
    help = 'Проверяет и исправляет флаги is_main для изображений постов и проектов'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Исправить флаги is_main (по умолчанию только проверка)',
        )
        parser.add_argument(
            '--posts-only',
            action='store_true',
            help='Обработать только посты',
        )
        parser.add_argument(
            '--projects-only',
            action='store_true',
            help='Обработать только проекты',
        )

    def handle(self, *args, **options):
        fix = options['fix']
        posts_only = options['posts_only']
        projects_only = options['projects_only']

        if not projects_only:
            self.stdout.write('🔍 Проверяю посты...')
            self.check_posts(fix)

        if not posts_only:
            self.stdout.write('🔍 Проверяю проекты...')
            self.check_projects(fix)

    def check_posts(self, fix=False):
        posts = Post.objects.prefetch_related('images').all()
        
        for post in posts:
            self.stdout.write(f'\n📝 Пост: {post.title}')
            
            # Проверяем все изображения поста
            images = post.images.all()
            if not images.exists():
                self.stdout.write('   ❌ Нет изображений')
                continue
            
            main_images = images.filter(is_main=True)
            real_images = images.filter(photo__isnull=False).exclude(photo__icontains='default-og-image')
            
            self.stdout.write(f'   📊 Всего изображений: {images.count()}')
            self.stdout.write(f'   🏷️  Главных изображений: {main_images.count()}')
            self.stdout.write(f'   🖼️  Реальных изображений: {real_images.count()}')
            
            # Проверяем каждое изображение
            for img in images:
                is_main = '✅' if img.is_main else '❌'
                is_default = '⚠️' if 'default-og-image' in str(img.photo) else '✅'
                self.stdout.write(f'      {is_main} {is_default} {img.photo or "Нет фото"}')
            
            # Если нужно исправить
            if fix and real_images.exists():
                # Сбрасываем все флаги is_main
                with transaction.atomic():
                    images.update(is_main=False)
                    
                    # Устанавливаем первое реальное изображение как главное
                    first_real = real_images.first()
                    first_real.is_main = True
                    first_real.save()
                    
                    self.stdout.write(f'   🔧 Исправлено: {first_real.photo} установлено как главное')

    def check_projects(self, fix=False):
        projects = Project.objects.prefetch_related('images').all()
        
        for project in projects:
            self.stdout.write(f'\n💼 Проект: {project.title}')
            
            # Проверяем все изображения проекта
            images = project.images.all()
            if not images.exists():
                self.stdout.write('   ❌ Нет изображений')
                continue
            
            main_images = images.filter(is_main=True)
            real_images = images.filter(photo__isnull=False).exclude(photo__icontains='default-og-image')
            
            self.stdout.write(f'   📊 Всего изображений: {images.count()}')
            self.stdout.write(f'   🏷️  Главных изображений: {main_images.count()}')
            self.stdout.write(f'   🖼️  Реальных изображений: {real_images.count()}')
            
            # Проверяем каждое изображение
            for img in images:
                is_main = '✅' if img.is_main else '❌'
                is_default = '⚠️' if 'default-og-image' in str(img.photo) else '✅'
                self.stdout.write(f'      {is_main} {is_default} {img.photo or "Нет фото"}')
            
            # Если нужно исправить
            if fix and real_images.exists():
                # Сбрасываем все флаги is_main
                with transaction.atomic():
                    images.update(is_main=False)
                    
                    # Устанавливаем первое реальное изображение как главное
                    first_real = real_images.first()
                    first_real.is_main = True
                    first_real.save()
                    
                    self.stdout.write(f'   🔧 Исправлено: {first_real.photo} установлено как главное') 