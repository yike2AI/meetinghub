from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.runner import run_ask
from app.agent.tools import topic_timeline
from app.db.bootstrap import get_default_user
from app.db.models import (
    AppUser,
    ChatMessage,
    ChatSession,
    ConfirmationTask,
    Entity,
    EntityRevision,
    Meeting,
    PlatformArtifact,
    Report,
    Space,
    Topic,
    TranscriptSegment,
)
from app.db.session import get_db
from app.schemas import (
    DingTalkPullBody,
    EntityCreate,
    EntityPatch,
    FeishuLinkBody,
    MessageCreate,
    ReportGenerate,
    ReportUpdate,
    SessionCreate,
    SpaceCreate,
    SpaceUpdate,
    ok,
)
from app.services.adapters import dingtalk, feishu
from app.services.confirm import confirm_all, confirm_entity, create_manual, expire_pending
from app.services.importing import import_batch_zip, import_single
from app.services.ingest import ingest_raw
from app.services.insights import space_insights
from app.services.report import generate_report
from app.services.search import hybrid_search
from app.services.sync import latest_sync, sync_space
from app.worker import enqueue_extraction

router = APIRouter(prefix="/api/v1")


def _meeting_out(m: Meeting) -> dict:
    return {
        "id": m.id,
        "space_id": m.space_id,
        "title": m.title,
        "held_at": m.held_at.isoformat(),
        "source": m.source,
        "status": m.status,
        "extraction_version": m.extraction_version,
        "participants": m.participants,
    }


def _entity_out(e: Entity) -> dict:
    return {
        "id": e.id,
        "meeting_id": e.meeting_id,
        "space_id": e.space_id,
        "topic_id": e.topic_id,
        "type": e.type,
        "payload": e.payload,
        "anchor_segment_ids": e.anchor_segment_ids,
        "status": e.status,
        "auto_committed": e.auto_committed,
        "confidence": float(e.confidence) if e.confidence is not None else None,
    }


@router.get("/auth/me")
async def auth_me(db: AsyncSession = Depends(get_db)):
    user = await get_default_user(db)
    spaces = (await db.execute(select(Space).where(Space.archived.is_(False)))).scalars().all()
    return ok(
        {
            "user": {"id": user.id, "name": user.name, "is_global_admin": user.is_global_admin},
            "spaces": [{"id": s.id, "name": s.name} for s in spaces],
            "dingtalk_configured": dingtalk.enabled(),
        }
    )


@router.get("/users")
async def list_users(db: AsyncSession = Depends(get_db)):
    await get_default_user(db)
    users = (await db.execute(select(AppUser))).scalars().all()
    return ok([{"id": u.id, "name": u.name} for u in users])


@router.get("/dashboard")
async def dashboard(db: AsyncSession = Depends(get_db)):
    await expire_pending(db)
    mc = (await db.execute(select(func.count()).select_from(Meeting))).scalar()
    pc = (
        await db.execute(select(func.count()).select_from(ConfirmationTask).where(ConfirmationTask.status == "pending"))
    ).scalar()
    ec = (
        await db.execute(select(func.count()).select_from(Entity).where(Entity.status != "deleted"))
    ).scalar()
    recent = (await db.execute(select(Meeting).order_by(Meeting.created_at.desc()).limit(8))).scalars().all()
    pending = (
        await db.execute(
            select(ConfirmationTask, Meeting).join(Meeting, Meeting.id == ConfirmationTask.meeting_id).where(
                ConfirmationTask.status == "pending"
            )
        )
    ).all()
    return ok(
        {
            "stats": {"meetings": mc or 0, "pending_confirmations": pc or 0, "entities": ec or 0},
            "recent_meetings": [_meeting_out(m) for m in recent],
            "pending_tasks": [
                {"meeting_id": m.id, "title": m.title, "deadline_at": t.deadline_at.isoformat(), "status": t.status}
                for t, m in pending
            ],
        }
    )


@router.get("/spaces")
async def list_spaces(db: AsyncSession = Depends(get_db)):
    spaces = (await db.execute(select(Space).where(Space.archived.is_(False)))).scalars().all()
    out = []
    for s in spaces:
        cnt = (await db.execute(select(func.count()).select_from(Meeting).where(Meeting.space_id == s.id))).scalar()
        out.append(
            {
                "id": s.id,
                "name": s.name,
                "security_level": s.security_level,
                "match_rules": s.match_rules,
                "report_enabled": s.report_enabled,
                "confirmer_user_id": s.confirmer_user_id,
                "meeting_count": cnt or 0,
                "dingtalk_configured": dingtalk.enabled(),
            }
        )
    return ok(out)


@router.post("/spaces")
async def create_space(body: SpaceCreate, db: AsyncSession = Depends(get_db)):
    user = await get_default_user(db)
    s = Space(
        name=body.name,
        security_level=body.security_level,
        confirmer_user_id=body.confirmer_user_id or user.id,
        match_rules=body.match_rules,
        report_enabled=body.report_enabled,
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)
    await sync_space(db, s)
    return ok({"id": s.id})


@router.get("/spaces/{space_id}")
async def get_space(space_id: int, db: AsyncSession = Depends(get_db)):
    s = await db.get(Space, space_id)
    if not s:
        return {"code": 404, "data": None, "msg": "空间不存在"}
    insights = await space_insights(db, space_id)
    syncs = await latest_sync(db, space_id)
    return ok(
        {
            "id": s.id,
            "name": s.name,
            "security_level": s.security_level,
            "match_rules": s.match_rules,
            "report_enabled": s.report_enabled,
            "confirmer_user_id": s.confirmer_user_id,
            "insights": insights,
            "sync_runs": syncs,
            "dingtalk_configured": dingtalk.enabled(),
        }
    )


@router.put("/spaces/{space_id}")
async def update_space(space_id: int, body: SpaceUpdate, db: AsyncSession = Depends(get_db)):
    s = await db.get(Space, space_id)
    if not s:
        return {"code": 404, "data": None, "msg": "空间不存在"}
    if body.name is not None:
        s.name = body.name
    if body.confirmer_user_id is not None:
        s.confirmer_user_id = body.confirmer_user_id
    if body.match_rules is not None:
        s.match_rules = body.match_rules
    if body.report_enabled is not None:
        s.report_enabled = body.report_enabled
    await db.commit()
    return ok({"id": s.id})


@router.post("/spaces/{space_id}/sync")
async def trigger_sync(space_id: int, db: AsyncSession = Depends(get_db)):
    s = await db.get(Space, space_id)
    if not s:
        return {"code": 404, "data": None, "msg": "空间不存在"}
    result = await sync_space(db, s)
    return ok(result)


@router.get("/spaces/{space_id}/meetings")
async def space_meetings(space_id: int, status: str | None = None, db: AsyncSession = Depends(get_db)):
    q = select(Meeting).where(Meeting.space_id == space_id).order_by(Meeting.held_at.desc())
    if status:
        q = q.where(Meeting.status == status)
    ms = (await db.execute(q)).scalars().all()
    return ok([_meeting_out(m) for m in ms])


@router.get("/spaces/{space_id}/insights")
async def insights(space_id: int, db: AsyncSession = Depends(get_db)):
    return ok(await space_insights(db, space_id))


@router.get("/meetings/{meeting_id}")
async def get_meeting(meeting_id: int, db: AsyncSession = Depends(get_db)):
    m = await db.get(Meeting, meeting_id)
    if not m:
        return {"code": 404, "data": None, "msg": "会议不存在"}
    ents = (
        await db.execute(select(Entity).where(Entity.meeting_id == meeting_id, Entity.status != "deleted"))
    ).scalars().all()
    arts = (
        await db.execute(select(PlatformArtifact).where(PlatformArtifact.meeting_id == meeting_id).order_by(PlatformArtifact.id))
    ).scalars().all()
    task = (await db.execute(select(ConfirmationTask).where(ConfirmationTask.meeting_id == meeting_id))).scalar_one_or_none()
    return ok(
        {
            **_meeting_out(m),
            "entities": [_entity_out(e) for e in ents],
            "artifacts": [
                {
                    "id": a.id,
                    "kind": a.kind,
                    "content": a.content,
                    "provider": ((a.raw or {}).get("provider") if isinstance(a.raw, dict) else None),
                }
                for a in arts
            ],
            "confirmation": None
            if not task
            else {"id": task.id, "deadline_at": task.deadline_at.isoformat(), "status": task.status},
        }
    )


@router.get("/meetings/{meeting_id}/transcript")
async def transcript(meeting_id: int, db: AsyncSession = Depends(get_db)):
    segs = (
        await db.execute(
            select(TranscriptSegment).where(TranscriptSegment.meeting_id == meeting_id).order_by(TranscriptSegment.seq)
        )
    ).scalars().all()
    return ok(
        [
            {
                "id": s.id,
                "seq": s.seq,
                "speaker_name": s.speaker_name,
                "start_ms": s.start_ms,
                "end_ms": s.end_ms,
                "text": s.text,
            }
            for s in segs
        ]
    )


@router.post("/meetings/import")
async def import_meeting(
    space_id: int = Form(...),
    title: str = Form(""),
    held_at: str = Form(""),
    participants: str = Form(""),
    paste_text: str = Form(""),
    file: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
):
    await get_default_user(db)
    if paste_text.strip():
        result = await import_single(
            space_id=space_id,
            title=title or "粘贴导入",
            held_at=held_at or None,
            participants=participants,
            filename="paste.txt",
            data=paste_text.encode("utf-8"),
        )
        return ok(result)
    if not file:
        return {"code": 422, "data": None, "msg": "请上传文件或粘贴文本"}
    data = await file.read()
    name = file.filename or "upload.txt"
    if name.lower().endswith(".zip"):
        return ok(await import_batch_zip(space_id, data))
    result = await import_single(
        space_id=space_id,
        title=title or name,
        held_at=held_at or None,
        participants=participants,
        filename=name,
        data=data,
    )
    return ok(result)


@router.post("/meetings/import/batch")
async def import_batch(space_id: int = Form(...), file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    await get_default_user(db)
    data = await file.read()
    return ok(await import_batch_zip(space_id, data))


@router.post("/meetings/feishu-link")
async def feishu_link(body: FeishuLinkBody, db: AsyncSession = Depends(get_db)):
    raw = await feishu.pull_from_url(body.url)
    meeting = await ingest_raw(db, raw, space_id=body.space_id)
    await enqueue_extraction(meeting.id)
    return ok(_meeting_out(meeting))


@router.post("/meetings/dingtalk-pull")
async def dingtalk_pull(body: DingTalkPullBody, db: AsyncSession = Depends(get_db)):
    if not dingtalk.enabled():
        return {
            "code": 422,
            "data": None,
            "msg": "钉钉企业应用未配置（缺少 DINGTALK_APP_KEY / APP_SECRET），无法自动拉取听记。请打开听记页导出 txt/srt，到「导入」页上传真实逐字稿。",
        }
    cid = dingtalk.parse_dingtalk_ref(body.conference_id)
    raw = await dingtalk.pull_texts(cid)
    if raw.get("empty"):
        return ok({"empty": True, "message": "无录制/无文本"})
    meeting = await ingest_raw(db, raw, space_id=body.space_id)
    await enqueue_extraction(meeting.id)
    return ok(_meeting_out(meeting))


@router.post("/meetings/{meeting_id}/re-extract")
async def re_extract(meeting_id: int, db: AsyncSession = Depends(get_db)):
    m = await db.get(Meeting, meeting_id)
    if not m:
        return {"code": 404, "data": None, "msg": "会议不存在"}
    await enqueue_extraction(meeting_id)
    return ok({"queued": True})


@router.get("/meetings/{meeting_id}/entities")
async def meeting_entities(meeting_id: int, status: str | None = None, db: AsyncSession = Depends(get_db)):
    q = select(Entity).where(Entity.meeting_id == meeting_id, Entity.status != "deleted")
    if status:
        q = q.where(Entity.status == status)
    rows = (await db.execute(q)).scalars().all()
    return ok([_entity_out(e) for e in rows])


@router.get("/confirmations/pending")
async def pending_confirmations(db: AsyncSession = Depends(get_db)):
    await expire_pending(db)
    rows = (
        await db.execute(
            select(ConfirmationTask, Meeting).join(Meeting, Meeting.id == ConfirmationTask.meeting_id).where(
                ConfirmationTask.status == "pending"
            )
        )
    ).all()
    return ok(
        [{"meeting_id": m.id, "title": m.title, "deadline_at": t.deadline_at.isoformat(), "status": t.status} for t, m in rows]
    )


@router.post("/entities/{entity_id}/confirm")
async def api_confirm(entity_id: int, db: AsyncSession = Depends(get_db)):
    e = await confirm_entity(db, entity_id, "confirm")
    return ok(_entity_out(e))


@router.put("/entities/{entity_id}")
async def api_edit_entity(entity_id: int, body: EntityPatch, db: AsyncSession = Depends(get_db)):
    e = await confirm_entity(db, entity_id, "edit", payload=body.payload)
    return ok(_entity_out(e))


@router.delete("/entities/{entity_id}")
async def api_delete_entity(entity_id: int, db: AsyncSession = Depends(get_db)):
    e = await confirm_entity(db, entity_id, "delete")
    return ok(_entity_out(e))


@router.post("/meetings/{meeting_id}/entities")
async def api_create_entity(meeting_id: int, body: EntityCreate, db: AsyncSession = Depends(get_db)):
    e = await create_manual(db, meeting_id, body.type, body.payload, body.anchor_segment_ids)
    return ok(_entity_out(e))


@router.post("/meetings/{meeting_id}/confirm-all")
async def api_confirm_all(meeting_id: int, db: AsyncSession = Depends(get_db)):
    n = await confirm_all(db, meeting_id)
    return ok({"confirmed": n})


@router.get("/entities/{entity_id}/revisions")
async def revisions(entity_id: int, db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(select(EntityRevision).where(EntityRevision.entity_id == entity_id).order_by(EntityRevision.id.desc()))
    ).scalars().all()
    return ok(
        [
            {"id": r.id, "action": r.action, "before": r.before, "after": r.after, "edited_at": r.edited_at.isoformat()}
            for r in rows
        ]
    )


@router.get("/entities")
async def list_entities(
    type: str | None = None,
    topic_id: int | None = None,
    space_id: int | None = None,
    person: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Entity).where(Entity.status != "deleted")
    if type:
        q = q.where(Entity.type == type)
    if topic_id:
        q = q.where(Entity.topic_id == topic_id)
    if space_id:
        q = q.where(Entity.space_id == space_id)
    rows = (await db.execute(q.order_by(Entity.id.desc()).limit(200))).scalars().all()
    items = [_entity_out(e) for e in rows]
    if person:
        items = [e for e in items if person in str(e["payload"])]
    return ok(items)


@router.get("/search")
async def search(q: str, space_id: int | None = None, db: AsyncSession = Depends(get_db)):
    return ok(await hybrid_search(db, q, space_id=space_id))


@router.get("/topics")
async def list_topics(space_id: int, db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Topic).where(Topic.space_id == space_id, Topic.merged_into.is_(None)))).scalars().all()
    return ok([{"id": t.id, "name": t.name, "summary": t.summary} for t in rows])


@router.get("/topics/{topic_id}/timeline")
async def timeline(topic_id: int, db: AsyncSession = Depends(get_db)):
    return ok(await topic_timeline(db, topic_id))


@router.get("/reports")
async def list_reports(space_id: int | None = None, db: AsyncSession = Depends(get_db)):
    q = select(Report).order_by(Report.created_at.desc())
    if space_id:
        q = q.where(Report.space_id == space_id)
    rows = (await db.execute(q)).scalars().all()
    return ok(
        [
            {
                "id": r.id,
                "space_id": r.space_id,
                "period_label": r.period_label,
                "status": r.status,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    )


@router.post("/reports/generate")
async def api_generate_report(body: ReportGenerate, db: AsyncSession = Depends(get_db)):
    r = await generate_report(db, body.space_id, body.period_label)
    return ok({"id": r.id})


@router.get("/reports/{report_id}")
async def get_report(report_id: int, db: AsyncSession = Depends(get_db)):
    r = await db.get(Report, report_id)
    if not r:
        return {"code": 404, "data": None, "msg": "报告不存在"}
    return ok(
        {
            "id": r.id,
            "space_id": r.space_id,
            "period_label": r.period_label,
            "content_md": r.content_md,
            "status": r.status,
            "meeting_ids": r.meeting_ids,
            "created_at": r.created_at.isoformat(),
        }
    )


@router.put("/reports/{report_id}")
async def update_report(report_id: int, body: ReportUpdate, db: AsyncSession = Depends(get_db)):
    r = await db.get(Report, report_id)
    if not r:
        return {"code": 404, "data": None, "msg": "报告不存在"}
    r.content_md = body.content_md
    await db.commit()
    return ok({"id": r.id})


@router.post("/agent/sessions")
async def create_session(body: SessionCreate, db: AsyncSession = Depends(get_db)):
    user = await get_default_user(db)
    s = ChatSession(
        user_id=user.id,
        space_id=body.space_id,
        topic_id=body.topic_id,
        title=body.title,
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return ok({"id": s.id, "space_id": s.space_id, "title": s.title})


@router.get("/agent/sessions")
async def list_sessions(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(ChatSession).order_by(ChatSession.id.desc()).limit(50))).scalars().all()
    return ok([{"id": s.id, "space_id": s.space_id, "title": s.title, "created_at": s.created_at.isoformat()} for s in rows])


@router.get("/agent/sessions/{session_id}")
async def get_session(session_id: int, db: AsyncSession = Depends(get_db)):
    s = await db.get(ChatSession, session_id)
    if not s:
        return {"code": 404, "data": None, "msg": "会话不存在"}
    msgs = (await db.execute(select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.id))).scalars().all()
    return ok(
        {
            "id": s.id,
            "space_id": s.space_id,
            "topic_id": s.topic_id,
            "title": s.title,
            "messages": [
                {"id": m.id, "role": m.role, "content_md": m.content_md, "citations": m.citations, "tool_trace": m.tool_trace}
                for m in msgs
            ],
        }
    )


@router.post("/agent/sessions/{session_id}/messages")
async def ask(session_id: int, body: MessageCreate, db: AsyncSession = Depends(get_db)):
    s = await db.get(ChatSession, session_id)
    if not s:
        return {"code": 404, "data": None, "msg": "会话不存在"}

    async def gen():
        async for chunk in run_ask(db, s, body.content):
            yield chunk

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.get("/agent/suggestions")
async def suggestions(space_id: int, db: AsyncSession = Depends(get_db)):
    topics = (await db.execute(select(Topic).where(Topic.space_id == space_id, Topic.merged_into.is_(None)).limit(1))).scalars().first()
    chips = [
        "有哪些承诺后来没了下文？",
        "哪些议题讨论多次但一直没有结论？",
        "目前最需要关注的风险是什么？",
        "最近一次会议的核心结论是什么？",
    ]
    if topics:
        chips.append(f"{topics.name} 这件事的来龙去脉？")
    return ok(chips)
