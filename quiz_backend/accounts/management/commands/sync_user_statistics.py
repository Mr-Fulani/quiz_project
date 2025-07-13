from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.core.cache import cache
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Синхронизирует статистику всех пользователей с реальными данными TaskStatistics'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user',
            type=str,
            help='Синхронизировать только конкретного пользователя по username'
        )
        parser.add_argument(
            '--clear-cache',
            action='store_true',
            help='Очистить кэш статистики после синхронизации'
        )

    def handle(self, *args, **options):
        username = options.get('user')
        clear_cache = options.get('clear_cache')
        
        if username:
            users = User.objects.filter(username=username)
            self.stdout.write(f"Синхронизация статистики для пользователя: {username}")
        else:
            users = User.objects.all()
            self.stdout.write("Синхронизация статистики для всех пользователей...")
        
        updated_count = 0
        error_count = 0
        
        for user in users:
            try:
                # Получаем старые значения для сравнения
                old_quizzes = user.quizzes_completed
                old_points = user.total_points
                
                # Обновляем статистику
                result = user.update_statistics()
                
                # Проверяем, изменились ли значения
                if (old_quizzes != result['quizzes_completed'] or 
                    old_points != result['total_points']):
                    updated_count += 1
                    self.stdout.write(
                        f"✓ {user.username}: квизов {old_quizzes}→{result['quizzes_completed']}, "
                        f"очков {old_points}→{result['total_points']}"
                    )
                else:
                    self.stdout.write(f"- {user.username}: без изменений")
                
                # Очищаем кэш если нужно
                if clear_cache:
                    user.invalidate_statistics_cache()
                    
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f"✗ Ошибка для {user.username}: {str(e)}")
                )
        
        # Итоговая статистика
        self.stdout.write("\n" + "="*50)
        self.stdout.write(f"Обработано пользователей: {users.count()}")
        self.stdout.write(f"Обновлено: {updated_count}")
        self.stdout.write(f"Ошибок: {error_count}")
        
        if clear_cache:
            self.stdout.write("Кэш статистики очищен")
        
        self.stdout.write(
            self.style.SUCCESS("Синхронизация завершена!")
        ) 