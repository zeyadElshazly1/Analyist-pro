"""
Celery application instance.

The broker and result backend both use Redis (already required for the
analysis cache).  Configure REDIS_URL in the environment; if unset the
module defaults to redis://localhost:6379/0 so local dev still works.
"""
import os

from celery import Celery

_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0") or "redis://localhost:6379/0"

celery_app = Celery(
    "analyistpro",
    broker=_REDIS_URL,
    backend=_REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    # One task at a time per worker process — analyses are CPU-heavy
    worker_prefetch_multiplier=1,
    # Ack only after task completes so a worker crash triggers a retry
    task_acks_late=True,
    # Keep results for 2 hours (same as analysis cache TTL)
    result_expires=7200,
    # Ignore results by default unless explicitly fetched
    task_ignore_result=False,
)
