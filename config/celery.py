import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('omnijob')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # Run greenhouse seed crawl every 6 hours
    sender.add_periodic_task(
        21600.0,  # 6 hours in seconds
        run_greenhouse_crawl.s(),
        name='greenhouse-crawl-every-6-hours',
    )

    # Run full discovery every 24 hours
    sender.add_periodic_task(
        86400.0,  # 24 hours
        run_full_discovery_task.s(),
        name='full-discovery-every-24-hours',
    )

    # State transition check every 3 hours
    sender.add_periodic_task(
        10800.0,  # 3 hours
        run_state_transitions.s(),
        name='state-transitions-every-3-hours',
    )