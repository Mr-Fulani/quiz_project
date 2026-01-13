from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from accounts.models import CustomUser
from tasks.models import TaskStatistics
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Обновляет статистику всех пользователей на основе их решений задач'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user',
            type=str,
            help='Обновить статистику только для конкретного пользователя (username)',
        )

    def handle(self, *args, **options):
        username = options.get('user')
        
        if username:
            users = CustomUser.objects.filter(username=username)
            if not users.exists():
                self.stdout.write(
                    self.style.ERROR(f'Пользователь с username "{username}" не найден')
                )
                return
        else:
            users = CustomUser.objects.all()

        updated_count = 0
        
        for user in users:
            try:
                # Получаем статистику пользователя
                # Считаем уникальные translation_group_id вместо количества записей
                # чтобы не учитывать дубликаты от синхронизации статистики между языками
                total_attempts = TaskStatistics.objects.filter(user=user).values('task__translation_group_id').distinct().count()
                successful_attempts = TaskStatistics.objects.filter(user=user, successful=True).values('task__translation_group_id').distinct().count()
                
                user_stats = {
                    'total_attempts': total_attempts,
                    'successful_attempts': successful_attempts
                }
                
                # Рассчитываем средний балл
                total_attempts = user_stats['total_attempts']
                successful_attempts = user_stats['successful_attempts']
                avg_score = round((successful_attempts / total_attempts * 100) if total_attempts > 0 else 0, 1)
                
                # Получаем любимую категорию
                favorite_topic = TaskStatistics.objects.filter(
                    user=user,
                    successful=True
                ).values('task__topic__name').annotate(count=Count('id')).order_by('-count').first()
                
                # Обновляем поля пользователя
                user.quizzes_completed = successful_attempts
                user.average_score = avg_score
                user.total_points = user.calculate_rating()
                
                if favorite_topic:
                    user.favorite_category = favorite_topic['task__topic__name']
                
                user.save(update_fields=['quizzes_completed', 'average_score', 'total_points', 'favorite_category'])
                
                # Очищаем кэш статистики
                user.invalidate_statistics_cache()
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Обновлена статистика пользователя {user.username}: '
                        f'квизов={user.quizzes_completed}, '
                        f'средний балл={user.average_score}%, '
                        f'очки={user.total_points}'
                    )
                )
                updated_count += 1
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Ошибка при обновлении статистики пользователя {user.username}: {e}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'Обновлена статистика для {updated_count} пользователей')
        ) 