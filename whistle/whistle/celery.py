import logging
import os

from celery import Celery
from celery.signals import worker_init

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "whistle.settings")

app = Celery("whistle")

app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks()


def restore_all_unacknowledged_messages():
    conn = app.connection(transport_options={"visibility_timeout": 0})
    qos = conn.channel().qos
    qos.restore_visible()
    logging.info("Unacknowledged messages restored")


@worker_init.connect
def configure(sender=None, conf=None, **kwargs):
    restore_all_unacknowledged_messages()
