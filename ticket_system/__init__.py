"""
ticket_system/__init__.py
==========================
This makes Celery's app available as soon as Django loads.
REPLACE your existing ticket_system/__init__.py with this file
(it's probably empty right now — just add these 2 lines).
"""

# This ensures the Celery app is always imported when Django starts,
# so that shared_task decorators (in tasks.py) work correctly.
from .celery import app as celery_app  # noqa: F401

__all__ = ("celery_app",)