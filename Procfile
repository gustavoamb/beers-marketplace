web: gunicorn --bind :8000 beers.wsgi:application
celery: celery -A beers worker
celery_beat: celery -A beers beat