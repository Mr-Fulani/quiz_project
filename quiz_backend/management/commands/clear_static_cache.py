from django.core.management.base import BaseCommand
from django.conf import settings
import os
import shutil


class Command(BaseCommand):
    help = 'Clear static files cache and force re-collection'

    def handle(self, *args, **options):
        staticfiles_dir = settings.STATIC_ROOT
        
        if os.path.exists(staticfiles_dir):
            self.stdout.write(f'Removing {staticfiles_dir}...')
            shutil.rmtree(staticfiles_dir)
            self.stdout.write(self.style.SUCCESS(f'✓ Removed {staticfiles_dir}'))
        
        # Recreate empty directory
        os.makedirs(staticfiles_dir, exist_ok=True)
        
        # Run collectstatic
        from django.core.management import call_command
        call_command('collectstatic', '--noinput')
        
        self.stdout.write(self.style.SUCCESS('✓ Static files cache cleared and re-collected')) 