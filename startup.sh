#!/bin/bash
pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate --noinput
celery -A config worker --loglevel=info --concurrency=32 -n worker1@%h &
celery -A config worker --loglevel=info --concurrency=32 -n worker2@%h &
celery -A config worker --loglevel=info --concurrency=32 -n worker3@%h &
celery -A config worker --loglevel=info --concurrency=32 -n worker4@%h &
# Only run beat on instance 0
if [ "$WEBSITE_INSTANCE_ID" = "$(cat /home/site/wwwroot/.beat_instance 2>/dev/null)" ] || [ ! -f /home/site/wwwroot/.beat_instance ]; then
    echo $WEBSITE_INSTANCE_ID > /home/site/wwwroot/.beat_instance
    celery -A config beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler &
fi
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers=4
