from django.core.management.base import BaseCommand
from accounts.models import CustomUser
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Обновляет статистику всех пользователей (очки и количество квизов)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help='Обновить статистику только для конкретного пользователя'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет обновлено без внесения изменений'
        )

    def handle(self, *args, **options):
        username = options.get('username')
        dry_run = options.get('dry_run')

        if username:
            try:
                user = CustomUser.objects.get(username=username)
                users = [user]
                self.stdout.write(f"Обновление статистики для пользователя: {username}")
            except CustomUser.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Пользователь {username} не найден"))
                return
        else:
            users = CustomUser.objects.all()
            self.stdout.write(f"Обновление статистики для всех пользователей ({users.count()} пользователей)")

        updated_count = 0
        for user in users:
            try:
                if dry_run:
                    old_stats = {
                        'quizzes_completed': user.quizzes_completed,
                        'total_points': user.total_points
                    }
                    new_stats = user.update_statistics()
                    
                    if (old_stats['quizzes_completed'] != new_stats['quizzes_completed'] or 
                        old_stats['total_points'] != new_stats['total_points']):
                        self.stdout.write(
                            f"Пользователь {user.username}: "
                            f"квизов {old_stats['quizzes_completed']} → {new_stats['quizzes_completed']}, "
                            f"очков {old_stats['total_points']} → {new_stats['total_points']}"
                        )
                        updated_count += 1
                else:
                    user.update_statistics()
                    updated_count += 1
                    self.stdout.write(f"Статистика пользователя {user.username} обновлена")
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Ошибка обновления статистики пользователя {user.username}: {e}")
                )

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(f"DRY RUN: Будет обновлено {updated_count} пользователей")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Успешно обновлена статистика для {updated_count} пользователей")
            ) 