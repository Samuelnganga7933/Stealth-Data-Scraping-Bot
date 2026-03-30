"""
core/queue.py — Redis job queue
Small jobs run immediately, large jobs run in background
Notifies you on WhatsApp/Telegram when done
"""

import asyncio
import uuid
from datetime import datetime
from enum import Enum
from typing import Callable, Optional, Any
from dataclasses import dataclass, field
from loguru import logger


class JobStatus(str, Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    DONE      = "done"
    FAILED    = "failed"


@dataclass
class Job:
    id:         str            = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name:       str            = ""
    status:     JobStatus      = JobStatus.PENDING
    created_at: str            = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str]  = None
    ended_at:   Optional[str]  = None
    result:     Any            = None
    error:      Optional[str]  = None
    notify_fn:  Optional[Callable] = field(default=None, repr=False)


class JobQueue:
    """
    Simple async in-memory job queue.
    Drop-in replacement — swap with Redis RQ for production.
    """

    def __init__(self, max_workers: int = 3):
        self._jobs:    dict[str, Job] = {}
        self._queue:   asyncio.Queue  = asyncio.Queue()
        self._workers: list           = []
        self.max_workers              = max_workers

    async def start(self):
        for _ in range(self.max_workers):
            w = asyncio.create_task(self._worker())
            self._workers.append(w)
        logger.info(f"Job queue started ({self.max_workers} workers)")

    async def stop(self):
        for w in self._workers:
            w.cancel()

    async def submit(
        self,
        name: str,
        coro_fn: Callable,
        args: tuple = (),
        kwargs: dict = None,
        notify_fn: Optional[Callable] = None,
    ) -> Job:
        job            = Job(name=name, notify_fn=notify_fn)
        self._jobs[job.id] = job
        await self._queue.put((job, coro_fn, args, kwargs or {}))
        logger.info(f"Job queued: [{job.id}] {name}")
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def all_jobs(self) -> list[Job]:
        return list(self._jobs.values())

    async def _worker(self):
        while True:
            job, fn, args, kwargs = await self._queue.get()
            job.status     = JobStatus.RUNNING
            job.started_at = datetime.now().isoformat()
            logger.info(f"Running job [{job.id}] {job.name}")

            try:
                job.result = await fn(*args, **kwargs)
                job.status = JobStatus.DONE
                logger.success(f"Job done [{job.id}] {job.name}")
            except Exception as e:
                job.status = JobStatus.FAILED
                job.error  = str(e)
                logger.error(f"Job failed [{job.id}] {job.name}: {e}")
            finally:
                job.ended_at = datetime.now().isoformat()
                if job.notify_fn:
                    try:
                        await job.notify_fn(job)
                    except Exception as e:
                        logger.warning(f"Notify failed for job [{job.id}]: {e}")
                self._queue.task_done()
