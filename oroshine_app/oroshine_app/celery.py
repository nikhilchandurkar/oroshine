import os
import time
from celery import Celery
from celery import shared_task

from celery.schedules import crontab
from celery.signals import (
    task_prerun, task_postrun, 
    task_failure, worker_ready
)
from prometheus_client import start_http_server  # ⚠️ FIX: Add missing import

# Correct Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'oroshine_app.settings')

# Create Celery app
app = Celery('oroshine_app')

# Load config from Django settings (CELERY_ prefix)
app.config_from_object('django.conf:settings', namespace='CELERY')

# Explicitly autodiscover tasks in your apps
app.autodiscover_tasks(['oroshine_webapp'])

# Periodic tasks
app.conf.beat_schedule = {
    'check-appointment-reminders-hourly': {
        'task': 'oroshine_webapp.tasks.check_and_send_reminders',
        'schedule': crontab(minute=0),
    },
    'cleanup-old-cache-daily': {
        'task': 'oroshine_webapp.tasks.cleanup_old_cache',
        'schedule': crontab(hour=2, minute=0),
    },
}

# Task defaults
app.conf.update(
    task_track_started=True,
    task_time_limit=30 * 60,
    task_soft_time_limit=25 * 60,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    task_default_retry_delay=30,
    task_max_retries=3,
)

# Start Prometheus exporter
@worker_ready.connect
def setup_prometheus_exporter(sender, **kwargs):
    """Start Prometheus metrics server on worker startup"""
    try:
        start_http_server(9808)
        print("✓ Prometheus exporter started on port 9808")
    except Exception as e:
        print(f"⚠ Failed to start Prometheus exporter: {e}")

@task_prerun.connect
def task_prerun_handler(task_id, task, *args, **kwargs):
    """Track task start time"""
    from oroshine_webapp.metrics import celery_task_total
    task.start_time = time.time()
    print(f"[Celery] Starting task: {task.name} (ID: {task_id})")

@task_postrun.connect
def task_postrun_handler(task_id, task, *args, **kwargs):
    """Track task completion and duration"""
    from oroshine_webapp.metrics import celery_task_duration, celery_task_total
    
    if hasattr(task, 'start_time'):
        duration = time.time() - task.start_time
        celery_task_duration.labels(task_name=task.name).observe(duration)
        print(f"[Celery] Completed task: {task.name} in {duration:.2f}s")
    
    celery_task_total.labels(task_name=task.name, status='success').inc()

@task_failure.connect
def task_failure_handler(task_id, exception, *args, **kwargs):
    """Track task failures"""
    from oroshine_webapp.metrics import celery_task_total
    
    task_name = kwargs.get('sender').name if 'sender' in kwargs else 'unknown'
    celery_task_total.labels(task_name=task_name, status='failure').inc()
    print(f"[Celery] Failed task: {task_name} - {exception}")

# @app.task(bind=True, ignore_result=True)
# def debug_task(self):
#     """Debug task to verify Celery is working"""
#     print(f'Request: {self.request!r}')
#     return 'Celery is working!'





#  cerely beat 



from celery.schedules import crontab

app.conf.beat_schedule = {
    # Runs every hour at minute 0
    'check-appointment-reminders-hourly': {
        'task': 'oroshine_webapp.tasks.check_and_send_reminders',
        'schedule': crontab(minute=0),
    },

    # Runs daily at 2:00 AM
    'cleanup-old-cache-daily': {
        'task': 'oroshine_webapp.tasks.cleanup_old_cache',
        'schedule': crontab(hour=2, minute=0),
    },

    # Runs every 10 seconds (learning / testing)
    'heartbeat-every-10-seconds': {
        'task': 'oroshine_webapp.tasks.heartbeat',
        'schedule': 1.0,
    },
}



# @shared_task
# def heartbeat():
#     print(" Celery Beat is alive!")
