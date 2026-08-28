from __future__ import annotations

import math
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Entity, EntityMention, Meeting, TranscriptSegment
from app.gateway import gateway
from pydantic import BaseModel, Field


class MentionOut(BaseModel):
    mentioned: bool = False
    mention_kind: str = "mentioned"


def _cosine(a, b) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a) or 1)
    nb = math.sqrt(sum(y * y for y in b) or 1)
    return dot / (na * nb)


def _summary(e: Entity) -> str:
    p = e.payload or {}
    if e.type == "commitment":
        return f"{p.get('item','')} {p.get('owner','')}"
    return f"{p.get('description','')} {p.get('impact','')}"


async def scan_mentions(db: AsyncSession, meeting_id: int) -> int:
    meeting = await db.get(Meeting, meeting_id)
    if not meeting or not meeting.space_id:
        return 0
    segs = (
        await db.execute(select(TranscriptSegment).where(TranscriptSegment.meeting_id == meeting_id))
    ).scalars().all()
    ents = (
        await db.execute(
            select(Entity).where(
                Entity.space_id == meeting.space_id,
                Entity.type.in_(["commitment", "risk"]),
                Entity.status != "deleted",
                Entity.meeting_id != meeting_id,
            )
        )
    ).scalars().all()
    n = 0
    for e in ents:
        e_vec = None
        if e.anchor_segment_ids:
            src = await db.get(TranscriptSegment, e.anchor_segment_ids[0])
            e_vec = list(src.embedding) if src and src.embedding else None
        if e_vec is None:
            vv = await gateway.embed([_summary(e)], db=db)
            e_vec = vv[0] if vv else None
        for s in segs:
            if not s.embedding or not e_vec:
                continue
            sim = _cosine(e_vec, list(s.embedding))
            if sim < 0.60:
                continue
            out = await gateway.extract(
                task="mention_judge",
                schema=MentionOut,
                system="判断段落是否在谈论该承诺/风险。拿不准的完成宣称请标 mentioned=true 且 mention_kind=progress。输出 JSON。",
                user=f"实体：{_summary(e)}\n段落：{s.text}\n输出 {{\"mentioned\":true/false,\"mention_kind\":\"progress|done_claim|revision|blocked|mentioned\"}}",
                db=db,
                meeting_id=meeting_id,
            )
            if not out.mentioned:
                continue
            kind = out.mention_kind if out.mention_kind in {"progress", "done_claim", "revision", "blocked", "mentioned"} else "mentioned"
            exists = (
                await db.execute(
                    select(EntityMention).where(EntityMention.entity_id == e.id, EntityMention.segment_id == s.id)
                )
            ).scalar_one_or_none()
            if exists:
                continue
            db.add(
                EntityMention(
                    entity_id=e.id,
                    meeting_id=meeting_id,
                    segment_id=s.id,
                    mention_kind=kind,
                    similarity=round(sim, 2),
                )
            )
            n += 1
    await db.commit()
    return n
