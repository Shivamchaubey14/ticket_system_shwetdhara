# ticket_system/celery.py
"""
Celery application for KSTS ticket system.
Place this file at:  ticket_system/celery.py
"""
import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ticket_system.settings")

app = Celery("ticket_system")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()