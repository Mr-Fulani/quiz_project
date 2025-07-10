#!/bin/bash

echo "🧹 Clearing static files cache..."

# Remove staticfiles directory
docker-compose exec quiz_backend rm -rf /app/staticfiles

# Recreate and collect static files
docker-compose exec quiz_backend python manage.py collectstatic --noinput

echo "✅ Static files cache cleared!"
echo "🔄 You may need to hard refresh your browser (Ctrl+F5 or Cmd+Shift+R)" 