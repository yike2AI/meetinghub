from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Entity, EntityMention, Meeting, Topic, TranscriptSegment
from app.services.search import hybrid_search

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_meetings",
            "description": "按关键词混合检索会议/逐字稿",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "space_id": {"type": "integer"},
                    "date_from": {"type": "string"},
                    "date_to": {"type": "string"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_transcript",
            "description": "读取会议逐字稿分段，单次最多50段",
            "parameters": {
                "type": "object",
                "properties": {
                    "meeting_id": {"type": "integer"},
                    "offset": {"type": "integer"},
                },
                "required": ["meeting_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_entities",
            "description": "检索决策/承诺/风险实体",
            "parameters": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "topic_id": {"type": "integer"},
                    "person": {"type": "string"},
                    "space_id": {"type": "integer"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_topic_timeline",
            "description": "议题时间线",
            "parameters": {"type": "object", "properties": {"topic_id": {"type": "integer"}}, "required": ["topic_id"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_entity_source",
            "description": "实体锚点原文",
            "parameters": {"type": "object", "properties": {"entity_id": {"type": "integer"}}, "required": ["entity_id"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_space_overview",
            "description": "空间概况",
            "parameters": {"type": "object", "properties": {"space_id": {"type": "integer"}}, "required": ["space_id"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_commitment_followup",
            "description": "承诺后续提及轨迹，研判悬空承诺",
            "parameters": {"type": "object", "properties": {"space_id": {"type": "integer"}}, "required": ["space_id"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_topic_health",
            "description": "议题健康：议而不决/决策改口",
            "parameters": {"type": "object", "properties": {"space_id": {"type": "integer"}}, "required": ["space_id"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_risk_evolution",
            "description": "风险演变轨迹",
            "parameters": {"type": "object", "properties": {"space_id": {"type": "integer"}, "topic_id": {"type": "integer"}}, "required": ["space_id"]},
        },
    },
]


def _exists_space(space_id: int, bound: int) -> None:
    if space_id != bound:
        raise PermissionError("资源不属于当前会话空间")


async def dispatch(db: AsyncSession, space_id: int, name: str, args: dict) -> dict:
    if name == "search_meetings":
        sid = args.get("space_id") or space_id
        _exists_space(int(sid), space_id)
        hits = await hybrid_search(db, args.get("query") or "", space_id=sid, limit=12)
        return {"hits": hits}
    if name == "get_transcript":
        mid = int(args["meeting_id"])
        m = await db.get(Meeting, mid)
        if not m or m.space_id != space_id:
            return {"error": "会议不存在"}
        offset = int(args.get("offset") or 0)
        segs = (
            await db.execute(
                select(TranscriptSegment)
                .where(TranscriptSegment.meeting_id == mid)
                .order_by(TranscriptSegment.seq)
                .offset(offset)
                .limit(50)
            )
        ).scalars().all()
        return {
            "meeting": {"id": m.id, "title": m.title, "held_at": m.held_at.isoformat()},
            "segments": [{"id": s.id, "seq": s.seq, "speaker_name": s.speaker_name, "text": s.text} for s in segs],
        }
    if name == "search_entities":
        q = select(Entity).where(Entity.space_id == space_id, Entity.status != "deleted")
        if args.get("type"):
            q = q.where(Entity.type == args["type"])
        if args.get("topic_id"):
            q = q.where(Entity.topic_id == int(args["topic_id"]))
        rows = (await db.execute(q.limit(50))).scalars().all()
        person = (args.get("person") or "").strip()
        items = []
        for e in rows:
            if person and person not in json.dumps(e.payload, ensure_ascii=False):
                continue
            items.append(
                {
                    "id": e.id,
                    "type": e.type,
                    "payload": e.payload,
                    "meeting_id": e.meeting_id,
                    "anchor_segment_ids": e.anchor_segment_ids,
                    "status": e.status,
                }
            )
        return {"entities": items}
    if name == "get_topic_timeline":
        return await topic_timeline(db, int(args["topic_id"]), space_id)
    if name == "get_entity_source":
        e = await db.get(Entity, int(args["entity_id"]))
        if not e or e.space_id != space_id:
            return {"error": "实体不存在"}
        segs = []
        for sid in e.anchor_segment_ids or []:
            s = await db.get(TranscriptSegment, sid)
            if s:
                segs.append({"segment_id": s.id, "meeting_id": s.meeting_id, "text": s.text, "speaker_name": s.speaker_name})
        return {"entity": {"id": e.id, "type": e.type, "payload": e.payload}, "segments": segs}
    if name == "get_space_overview":
        mc = (await db.execute(select(func.count()).select_from(Meeting).where(Meeting.space_id == space_id))).scalar()
        topics = (await db.execute(select(Topic).where(Topic.space_id == space_id, Topic.merged_into.is_(None)))).scalars().all()
        recent = (
            await db.execute(select(Meeting).where(Meeting.space_id == space_id).order_by(Meeting.held_at.desc()).limit(5))
        ).scalars().all()
        return {
            "meeting_count": mc,
            "topics": [{"id": t.id, "name": t.name} for t in topics],
            "recent": [{"id": m.id, "title": m.title, "held_at": m.held_at.isoformat()} for m in recent],
        }
    if name == "analyze_commitment_followup":
        ents = (
            await db.execute(
                select(Entity).where(Entity.space_id == space_id, Entity.type == "commitment", Entity.status != "deleted")
            )
        ).scalars().all()
        items = []
        now = datetime.now(timezone.utc)
        for e in ents:
            mentions = (
                await db.execute(select(EntityMention).where(EntityMention.entity_id == e.id).order_by(EntityMention.created_at.desc()))
            ).scalars().all()
            last = mentions[0].created_at if mentions else e.created_at
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            silent = (now - last).days
            items.append(
                {
                    "entity_id": e.id,
                    "item": (e.payload or {}).get("item"),
                    "owner": (e.payload or {}).get("owner"),
                    "last_kind": mentions[0].mention_kind if mentions else None,
                    "silent_days": silent,
                    "mention_count": len(mentions),
                    "meeting_id": e.meeting_id,
                    "anchor_segment_ids": e.anchor_segment_ids,
                }
            )
        items.sort(key=lambda x: x["silent_days"], reverse=True)
        return {"commitments": items}
    if name == "analyze_topic_health":
        topics = (await db.execute(select(Topic).where(Topic.space_id == space_id, Topic.merged_into.is_(None)))).scalars().all()
        out = []
        for t in topics:
            ents = (await db.execute(select(Entity).where(Entity.topic_id == t.id, Entity.status != "deleted"))).scalars().all()
            mids = {e.meeting_id for e in ents}
            has_decision = any(e.type == "decision" for e in ents)
            revisions = (
                await db.execute(
                    select(func.count()).select_from(EntityMention).where(
                        EntityMention.entity_id.in_([e.id for e in ents] or [0]),
                        EntityMention.mention_kind == "revision",
                    )
                )
            ).scalar() or 0
            out.append(
                {
                    "topic_id": t.id,
                    "name": t.name,
                    "meeting_count": len(mids),
                    "has_decision": has_decision,
                    "revision_mentions": int(revisions),
                    "stalled": len(mids) >= 3 and not has_decision,
                }
            )
        return {"topics": out}
    if name == "analyze_risk_evolution":
        q = select(Entity).where(Entity.space_id == space_id, Entity.type == "risk", Entity.status != "deleted")
        if args.get("topic_id"):
            q = q.where(Entity.topic_id == int(args["topic_id"]))
        ents = (await db.execute(q)).scalars().all()
        items = []
        for e in ents:
            mentions = (await db.execute(select(EntityMention).where(EntityMention.entity_id == e.id))).scalars().all()
            items.append(
                {
                    "entity_id": e.id,
                    "description": (e.payload or {}).get("description"),
                    "trajectory": [{"kind": m.mention_kind, "meeting_id": m.meeting_id, "segment_id": m.segment_id} for m in mentions],
                    "meeting_id": e.meeting_id,
                    "anchor_segment_ids": e.anchor_segment_ids,
                }
            )
        return {"risks": items}
    return {"error": f"unknown tool {name}"}


async def topic_timeline(db: AsyncSession, topic_id: int, space_id: int | None = None) -> dict:
    t = await db.get(Topic, topic_id)
    if not t or (space_id and t.space_id != space_id):
        return {"error": "议题不存在"}
    ents = (await db.execute(select(Entity).where(Entity.topic_id == topic_id, Entity.status != "deleted"))).scalars().all()
    by_m: dict[int, list] = {}
    for e in ents:
        by_m.setdefault(e.meeting_id, []).append(e)
    nodes = []
    for mid, elist in by_m.items():
        m = await db.get(Meeting, mid)
        if not m:
            continue
        nodes.append(
            {
                "meeting": {"id": m.id, "title": m.title, "held_at": m.held_at.isoformat()},
                "entities": [
                    {"id": e.id, "type": e.type, "payload": e.payload, "anchor_segment_ids": e.anchor_segment_ids, "status": e.status}
                    for e in elist
                ],
            }
        )
    nodes.sort(key=lambda n: n["meeting"]["held_at"])
    return {"topic": {"id": t.id, "name": t.name, "summary": t.summary}, "nodes": nodes}
