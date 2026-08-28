"""
Celery app + task definitions.

Tasks:
  - run_workflow_task       → executes a workflow execution
  - poll_trigger_task       → polling-based triggers (email IMAP, etc.)
  - refresh_tokens_task     → periodic token refresh check
  - cleanup_executions_task → prune old execution rows
"""
import asyncio
from celery import Celery
from celery.schedules import crontab
from kombu import Queue

from core.config import settings

celery_app = Celery(
    "autoflow",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "workers.tasks.run_workflow_task": {"queue": "workflows"},
        "workers.tasks.poll_trigger_task": {"queue": "polling"},
        "workers.tasks.refresh_tokens_task": {"queue": "maintenance"},
        "workers.tasks.cleanup_executions_task": {"queue": "maintenance"},
    },
    task_queues=[
        Queue("workflows", routing_key="workflows"),
        Queue("polling", routing_key="polling"),
        Queue("maintenance", routing_key="maintenance"),
    ],
    beat_schedule={
        "poll-triggers-every-60s": {
            "task": "workers.tasks.poll_trigger_task",
            "schedule": 60.0,
        },
        "refresh-tokens-every-hour": {
            "task": "workers.tasks.refresh_tokens_task",
            "schedule": crontab(minute=0),
        },
        "cleanup-old-executions-daily": {
            "task": "workers.tasks.cleanup_executions_task",
            "schedule": crontab(hour=2, minute=0),
        },
    },
)


def _run_async(coro):
    """Run an async coroutine from sync Celery task."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


from celery import Task


class WorkflowTask(Task):
    """Custom task class so we can hook final-failure (retries exhausted) into the DLQ."""

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        # Called once, after the LAST retry attempt fails (or autoretry is exhausted).
        execution_id = args[0] if len(args) > 0 else kwargs.get("execution_id")
        workflow_definition = args[1] if len(args) > 1 else kwargs.get("workflow_definition", {})
        trigger_data = args[2] if len(args) > 2 else kwargs.get("trigger_data", {})

        from core.dlq import push_to_dlq
        _run_async(push_to_dlq(
            execution_id=execution_id,
            workflow_id=workflow_definition.get("id") if isinstance(workflow_definition, dict) else None,
            org_id=kwargs.get("org_id"),
            task_name=self.name,
            payload={
                "workflow_definition": workflow_definition,
                "trigger_data": trigger_data,
            },
            error=exc,
        ))


@celery_app.task(
    name="workers.tasks.run_workflow_task",
    base=WorkflowTask,
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def run_workflow_task(self, execution_id: str, workflow_definition: dict, trigger_data: dict):
    from core.execution_engine import execute_workflow
    _run_async(execute_workflow(execution_id, workflow_definition, trigger_data))


@celery_app.task(name="workers.tasks.poll_trigger_task")
def poll_trigger_task():
    from triggers.polling import run_all_pollers
    _run_async(run_all_pollers())


@celery_app.task(name="workers.tasks.refresh_tokens_task")
def refresh_tokens_task():
    from workers.maintenance import refresh_expiring_tokens
    _run_async(refresh_expiring_tokens())


@celery_app.task(name="workers.tasks.cleanup_executions_task")
def cleanup_executions_task(days_to_keep: int = 30):
    from workers.maintenance import cleanup_old_executions
    _run_async(cleanup_old_executions(days_to_keep))
