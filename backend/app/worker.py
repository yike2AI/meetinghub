from __future__ import annotations

import asyncio

from arq.connections import RedisSettings
from arq.cron import cron

from app.config import settings
from app.db.session import SessionLocal


def redis_settings() -> RedisSettings:
    url = settings.redis_url
    # redis://localhost:6379/0
    return RedisSettings.from_dsn(url)


async def enqueue_extraction(meeting_id: int) -> None:
    try:
        from arq import create_pool

        redis = await create_pool(redis_settings())
        try:
            await redis.enqueue_job("extract_meeting", meeting_id)
            return
        finally:
            await redis.close(close_connection_pool=True)
    except Exception:
        asyncio.create_task(_extract_inline(meeting_id))


async def _extract_inline(meeting_id: int) -> None:
    from app.services.extract import run_extraction

    async with SessionLocal() as db:
        await run_extraction(db, meeting_id)


async def extract_meeting(ctx, meeting_id: int) -> None:
    from app.services.extract import run_extraction

    async with SessionLocal() as db:
        await run_extraction(db, meeting_id)


async def expire_confirmations(ctx) -> None:
    from app.services.confirm import expire_pending

    async with SessionLocal() as db:
        await expire_pending(db)


async def poll_sync(ctx) -> None:
    from app.services.sync import sync_all_spaces

    async with SessionLocal() as db:
        await sync_all_spaces(db)


class WorkerSettings:
    functions = [extract_meeting]
    cron_jobs = [
        cron(expire_confirmations, minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}, run_at_startup=True),
        cron(poll_sync, minute={0, 15, 30, 45}, run_at_startup=False),
    ]
    redis_settings = redis_settings()
    max_jobs = 1
