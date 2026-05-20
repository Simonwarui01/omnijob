#!/bin/bash
pip install -r requirements.txt
python manage.py migrate --noinput
gunicorn config.wsgi:application --bind 0.0.0.0:8000
