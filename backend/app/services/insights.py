from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Entity, EntityMention, Meeting, Topic


async def space_insights(db: AsyncSession, space_id: int) -> dict:
    now = datetime.now(timezone.utc)
    hang_days = 45
    commitments = (
        await db.execute(
            select(Entity).where(
                Entity.space_id == space_id,
                Entity.type == "commitment",
                Entity.status.in_(["confirmed", "auto_committed", "ai_extracted"]),
            )
        )
    ).scalars().all()
    hanging = []
    for e in commitments:
        last = (
            await db.execute(
                select(func.max(EntityMention.created_at)).where(EntityMention.entity_id == e.id)
            )
        ).scalar()
        ref = last or e.created_at
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=timezone.utc)
        if now - ref >= timedelta(days=hang_days):
            hanging.append(e.id)
    topics = (await db.execute(select(Topic).where(Topic.space_id == space_id, Topic.merged_into.is_(None)))).scalars().all()
    stalled = []
    for t in topics:
        meetings = (
            await db.execute(
                select(func.count(func.distinct(Entity.meeting_id))).where(Entity.topic_id == t.id, Entity.status != "deleted")
            )
        ).scalar() or 0
        decisions = (
            await db.execute(
                select(func.count()).select_from(Entity).where(Entity.topic_id == t.id, Entity.type == "decision", Entity.status != "deleted")
            )
        ).scalar() or 0
        if meetings >= 3 and decisions == 0:
            stalled.append(t.id)
    since = now - timedelta(days=60)
    active_risks = (
        await db.execute(
            select(func.count(func.distinct(EntityMention.entity_id)))
            .join(Entity, Entity.id == EntityMention.entity_id)
            .where(
                Entity.space_id == space_id,
                Entity.type == "risk",
                EntityMention.created_at >= since,
                EntityMention.mention_kind != "done_claim",
            )
        )
    ).scalar() or 0
    if active_risks == 0:
        active_risks = (
            await db.execute(
                select(func.count()).select_from(Entity).where(
                    Entity.space_id == space_id,
                    Entity.type == "risk",
                    Entity.status != "deleted",
                    Entity.created_at >= since,
                )
            )
        ).scalar() or 0
    return {
        "hanging_commitments": len(hanging),
        "stalled_topics": len(stalled),
        "active_risks": int(active_risks),
        "prompts": {
            "hanging": "有哪些承诺后来没了下文？",
            "stalled": "哪些议题讨论多次但一直没有结论？",
            "risks": "目前最需要关注的风险是什么？",
        },
    }
