#!/bin/bash
python manage.py collectstatic --noinput
python manage.py migrate --noinput
celery -A config worker --loglevel=info --concurrency=8 -n worker1@%h &
celery -A config worker --loglevel=info --concurrency=8 -n worker2@%h &
celery -A config beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler &
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers=4
