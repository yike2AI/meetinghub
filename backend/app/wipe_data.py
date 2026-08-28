"""Wipe all POC business data. Keep the default user."""
import asyncio

from sqlalchemy import text

from app.db.bootstrap import get_default_user
from app.db.session import SessionLocal, engine


TABLES = [
    "entity_mention",
    "entity_revision",
    "chat_message",
    "chat_session",
    "confirmation_task",
    "entity",
    "platform_artifact",
    "transcript_segment",
    "report",
    "topic",
    "sync_run",
    "llm_usage",
    "audit_log",
    "meeting",
    "space_member",
    "space",
]


async def main() -> None:
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE " + ", ".join(TABLES) + " RESTART IDENTITY CASCADE"))
    async with SessionLocal() as db:
        await get_default_user(db)
    print("wiped")


if __name__ == "__main__":
    asyncio.run(main())
