from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AppUser, Base
from app.db.session import engine
from sqlalchemy import text


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    for sql in (
        "CREATE INDEX IF NOT EXISTS idx_seg_fts ON transcript_segment USING GIN (search_vector)",
        "CREATE INDEX IF NOT EXISTS idx_seg_vec ON transcript_segment USING hnsw (embedding vector_cosine_ops)",
        "CREATE INDEX IF NOT EXISTS idx_entity_space ON entity(space_id, type, status)",
        "CREATE INDEX IF NOT EXISTS idx_mention_entity ON entity_mention(entity_id)",
    ):
        try:
            async with engine.begin() as conn:
                await conn.execute(text(sql))
        except Exception as exc:
            print("skip index:", sql, exc)


async def get_default_user(db: AsyncSession) -> AppUser:
    u = (await db.execute(select(AppUser).order_by(AppUser.id).limit(1))).scalar_one_or_none()
    if u:
        return u
    u = AppUser(name="POC 管理员", is_global_admin=True)
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u
