"""Arq worker: processa jobs assíncronos disparados pela API.

Rodado como serviço separado no docker-compose. Execução manual:

    uv run arq app.worker.WorkerSettings
"""

from arq.connections import RedisSettings

from .config import get_settings
from .jobs import process_summary


def _redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(get_settings().redis_url)


class WorkerSettings:
    functions = [process_summary]
    redis_settings = _redis_settings()
    # Folga para docs grandes que caem no map-reduce da fase 3.
    job_timeout = 600
    keep_result = 3600
    max_jobs = 4
