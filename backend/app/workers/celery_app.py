from celery import Celery
from kombu import Queue

from app.core.config import get_settings

# One pool per queue in pilot/prod (docs/ARCHITECTURE.md §8); a single local worker consumes all.
QUEUES = ("ingest", "ocr", "llm", "core", "report")

celery_app = Celery("tenderai", broker=get_settings().redis_url, include=["app.workers.tasks"])
celery_app.conf.update(
    task_queues=[Queue(name) for name in QUEUES],
    task_default_queue="core",
    # Pipeline state lives in Postgres (pipeline_steps); Celery only executes, results are dropped.
    task_ignore_result=True,
    # Pages and LLM calls are long-running: hand out one task at a time and ack only on completion.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    timezone="Asia/Tashkent",
)


@celery_app.task(name="system.ping")
def ping() -> str:
    return "pong"
