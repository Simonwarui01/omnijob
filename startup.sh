#!/bin/bash
pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate --noinput
celery -A config worker --loglevel=info --concurrency=16 -n worker1@%h &
celery -A config worker --loglevel=info --concurrency=16 -n worker2@%h &
celery -A config beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler &
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers=8
