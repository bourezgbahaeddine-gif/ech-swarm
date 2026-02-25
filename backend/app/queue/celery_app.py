"""Celery application for AI/background workloads."""

from __future__ import annotations

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "echorouk_workers",
    broker=settings.redis_queue_url,
    backend=settings.redis_queue_url,
    include=[
        "app.queue.tasks.ai_tasks",
        "app.queue.tasks.pipeline_tasks",
    ],
)

celery_app.conf.update(
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    broker_connection_retry_on_startup=True,
    task_default_queue=settings.queue_default_name,
    task_default_exchange=settings.queue_default_name,
    task_default_routing_key=settings.queue_default_name,
    task_routes={
        "app.queue.tasks.ai_tasks.run_editorial_links_job": {"queue": "ai_links"},
        "app.queue.tasks.ai_tasks.*": {"queue": "ai_quality"},
        "app.queue.tasks.pipeline_tasks.run_scout_batch": {"queue": "ai_router"},
        "app.queue.tasks.pipeline_tasks.run_router_batch": {"queue": "ai_router"},
        "app.queue.tasks.pipeline_tasks.run_scribe_batch": {"queue": "ai_scribe"},
        "app.queue.tasks.pipeline_tasks.run_trends_scan": {"queue": "ai_trends"},
        "app.queue.tasks.pipeline_tasks.run_published_monitor_scan": {"queue": "ai_quality"},
        "app.queue.tasks.pipeline_tasks.run_document_intel_extract_job": {"queue": "ai_quality"},
        "app.queue.tasks.pipeline_tasks.run_script_generate_job": {"queue": "ai_scripts"},
        "app.queue.tasks.pipeline_tasks.run_msi_job": {"queue": "ai_msi"},
        "app.queue.tasks.pipeline_tasks.run_simulator_job": {"queue": "ai_simulator"},
    },
)
