from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.bootstrap import get_default_user
from app.db.models import ConfirmationTask, Entity, EntityRevision, Meeting


async def expire_pending(db: AsyncSession) -> int:
    now = datetime.now(timezone.utc)
    tasks = (
        await db.execute(select(ConfirmationTask).where(ConfirmationTask.status == "pending", ConfirmationTask.deadline_at <= now))
    ).scalars().all()
    n = 0
    user = await get_default_user(db)
    for t in tasks:
        ents = (
            await db.execute(
                select(Entity).where(Entity.meeting_id == t.meeting_id, Entity.status == "ai_extracted")
            )
        ).scalars().all()
        for e in ents:
            before = {"status": e.status, "payload": e.payload}
            e.status = "auto_committed"
            e.auto_committed = True
            db.add(
                EntityRevision(
                    entity_id=e.id,
                    editor_user_id=user.id,
                    action="confirm",
                    before=before,
                    after={"status": "auto_committed", "payload": e.payload},
                )
            )
        t.status = "expired"
        m = await db.get(Meeting, t.meeting_id)
        if m:
            m.status = "done"
        n += 1
    if n:
        await db.commit()
    return n


async def confirm_entity(db: AsyncSession, entity_id: int, action: str, payload: dict | None = None) -> Entity:
    await expire_pending(db)
    e = await db.get(Entity, entity_id)
    if not e:
        raise ValueError("实体不存在")
    user = await get_default_user(db)
    before = {"status": e.status, "payload": e.payload, "type": e.type}
    if action == "confirm":
        e.status = "confirmed"
    elif action == "edit":
        if payload is not None:
            e.payload = payload
        e.status = "confirmed"
    elif action == "delete":
        e.status = "deleted"
    db.add(EntityRevision(entity_id=e.id, editor_user_id=user.id, action=action if action != "edit" else "edit", before=before, after={"status": e.status, "payload": e.payload}))
    await db.commit()
    await db.refresh(e)
    await _maybe_close_task(db, e.meeting_id)
    return e


async def confirm_all(db: AsyncSession, meeting_id: int) -> int:
    await expire_pending(db)
    ents = (
        await db.execute(select(Entity).where(Entity.meeting_id == meeting_id, Entity.status == "ai_extracted"))
    ).scalars().all()
    n = 0
    for e in ents:
        await confirm_entity(db, e.id, "confirm")
        n += 1
    return n


async def create_manual(db: AsyncSession, meeting_id: int, type_: str, payload: dict, anchors: list[int]) -> Entity:
    m = await db.get(Meeting, meeting_id)
    if not m or not m.space_id:
        raise ValueError("会议不存在")
    user = await get_default_user(db)
    e = Entity(
        meeting_id=meeting_id,
        space_id=m.space_id,
        type=type_,
        payload=payload,
        anchor_segment_ids=anchors,
        status="confirmed",
        extraction_version=m.extraction_version or 1,
    )
    db.add(e)
    await db.flush()
    db.add(EntityRevision(entity_id=e.id, editor_user_id=user.id, action="create_manual", before=None, after={"payload": payload}))
    await db.commit()
    await db.refresh(e)
    return e


async def _maybe_close_task(db: AsyncSession, meeting_id: int) -> None:
    left = (
        await db.execute(select(Entity).where(Entity.meeting_id == meeting_id, Entity.status == "ai_extracted"))
    ).scalars().first()
    if left:
        return
    t = (await db.execute(select(ConfirmationTask).where(ConfirmationTask.meeting_id == meeting_id))).scalar_one_or_none()
    if t and t.status == "pending":
        t.status = "done"
    m = await db.get(Meeting, meeting_id)
    if m:
        m.status = "done"
    await db.commit()
    from app.db.models import Space
    from app.services.report import generate_report

    if m and m.space_id:
        sp = await db.get(Space, m.space_id)
        if sp and sp.report_enabled:
            try:
                await generate_report(db, m.space_id)
            except Exception:
                pass
