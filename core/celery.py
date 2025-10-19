import os

from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

# Create a Celery app instance
app = Celery("market_watch")

# Configure Celery using Django settings
app.config_from_object("django.conf:settings", namespace="CELERY")

# Automatically discover tasks in all registered Django apps
app.autodiscover_tasks()
