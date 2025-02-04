from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from accounts.models import UserSettings

User = get_user_model()

class Command(BaseCommand):
    help = 'Creates UserSettings for existing users'

    def handle(self, *args, **kwargs):
        users = User.objects.all()
        created_count = 0
        
        for user in users:
            settings, created = UserSettings.objects.get_or_create(user=user)
            if created:
                created_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created settings for {created_count} users'
            )
        ) 