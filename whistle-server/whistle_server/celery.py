import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "whistle_server.settings")

app = Celery("whistle_server")

app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks()
