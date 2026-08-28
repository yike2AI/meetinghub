from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import String, cast, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Meeting, Space, SyncRun
from app.services.adapters import dingtalk, feishu
from app.services.ingest import ingest_raw
from app.services.notify import notify_pull_fail


async def _log(db: AsyncSession, space_id: int | None, channel: str, status: str, message: str) -> None:
    run = SyncRun(space_id=space_id, channel=channel, status=status, message=message, finished_at=datetime.now(timezone.utc))
    db.add(run)
    await db.commit()


async def latest_sync(db: AsyncSession, space_id: int) -> list[dict]:
    rows = (
        await db.execute(select(SyncRun).where(SyncRun.space_id == space_id).order_by(SyncRun.started_at.desc()).limit(8))
    ).scalars().all()
    return [
        {
            "channel": r.channel,
            "status": r.status,
            "message": r.message,
            "started_at": r.started_at.isoformat() if r.started_at else None,
        }
        for r in rows
    ]


async def sync_space(db: AsyncSession, space: Space) -> dict:
    pulled = 0
    errors: list[str] = []
    for rule in space.match_rules or []:
        rtype = rule.get("type")
        if rtype == "feishu_owner_sync":
            try:
                items = await feishu.search_minutes(keyword=rule.get("keyword") or "", since=rule.get("since") or "")
                for it in items:
                    token = it.get("token") or it.get("minute_token") or it.get("minuteToken") or it.get("id")
                    if not token and isinstance(it.get("url"), str):
                        try:
                            token = feishu.extract_minute_token(it["url"])
                        except Exception:
                            token = None
                    if not token:
                        continue
                    exists = (
                        await db.execute(
                            select(Meeting).where(
                                Meeting.source == "feishu",
                                cast(Meeting.source_ref["minute_token"], String) == str(token),
                            )
                        )
                    ).scalar_one_or_none()
                    if exists:
                        continue
                    raw = await feishu.export_minute(str(token))
                    m = await ingest_raw(db, raw, space_id=space.id)
                    from app.worker import enqueue_extraction

                    await enqueue_extraction(m.id)
                    pulled += 1
                await _log(db, space.id, "feishu", "ok", f"新入库 {pulled} 场")
            except Exception as e:
                errors.append(str(e))
                await _log(db, space.id, "feishu", "error", str(e))
                await notify_pull_fail(f"飞书同步失败：{e}")
        if rtype == "recurring_meeting_id":
            cid = rule.get("value")
            if cid and dingtalk.enabled():
                try:
                    raw = await dingtalk.pull_texts(cid)
                    if raw.get("empty"):
                        await _log(db, space.id, "dingtalk", "empty", "无录制/无文本")
                    else:
                        m = await ingest_raw(db, raw, space_id=space.id)
                        from app.worker import enqueue_extraction

                        await enqueue_extraction(m.id)
                        pulled += 1
                        await _log(db, space.id, "dingtalk", "ok", f"conference {cid}")
                except Exception as e:
                    errors.append(str(e))
                    await _log(db, space.id, "dingtalk", "error", str(e))
            elif cid and not dingtalk.enabled():
                await _log(db, space.id, "dingtalk", "skipped", "待配置企业应用凭据")
        if rtype == "title_keyword" and dingtalk.enabled():
            await _log(db, space.id, "dingtalk", "skipped", "标题关键词轮询需企业凭据，POC 以 conferenceId 为主")
    return {"pulled": pulled, "errors": errors}


async def sync_all_spaces(db: AsyncSession) -> None:
    spaces = (await db.execute(select(Space).where(Space.archived.is_(False)))).scalars().all()
    for sp in spaces:
        try:
            await sync_space(db, sp)
        except Exception as e:
            await notify_pull_fail(f"空间 {sp.name} 同步失败：{e}")
