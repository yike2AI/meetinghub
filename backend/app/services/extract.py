from __future__ import annotations

import math
import re
from typing import Any, Literal

from pydantic import BaseModel, Field
from rapidfuzz import fuzz
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.bootstrap import get_default_user
from app.db.models import ConfirmationTask, Entity, Meeting, PlatformArtifact, Topic, TranscriptSegment
from app.gateway import gateway, prompt_text
from app.config import settings
from datetime import datetime, timedelta, timezone


class Candidate(BaseModel):
    type: Literal["decision", "commitment", "risk"]
    payload: dict[str, Any]
    evidence_quotes: list[str] = Field(default_factory=list)
    seg_ids: list[int] = Field(default_factory=list)
    confidence: float = 0.6


class ExtractOut(BaseModel):
    items: list[Candidate] = Field(default_factory=list)


def _norm(s: str) -> str:
    return re.sub(r"[\s\W_]+", "", s or "", flags=re.UNICODE)


def quote_matches(quote: str, text: str) -> bool:
    if not quote or not text:
        return False
    if quote in text:
        return True
    nq, nt = _norm(quote), _norm(text)
    if nq and nq in nt:
        return True
    return fuzz.partial_ratio(quote, text) >= 90


def validate_anchors(item: Candidate, seg_map: dict[int, TranscriptSegment]) -> list[int]:
    ok_ids: list[int] = []
    quotes = item.evidence_quotes or []
    if not quotes:
        return []
    target_ids = item.seg_ids or list(seg_map.keys())
    for q in quotes:
        hit = False
        for sid in target_ids:
            seg = seg_map.get(sid)
            if seg and quote_matches(q, seg.text):
                ok_ids.append(sid)
                hit = True
                break
        if not hit:
            for sid, seg in seg_map.items():
                if quote_matches(q, seg.text):
                    ok_ids.append(sid)
                    hit = True
                    break
        if not hit:
            return []
    return list(dict.fromkeys(ok_ids))


def chunk_segments(segments: list[TranscriptSegment], max_chars: int = 6000, overlap: int = 400) -> list[list[TranscriptSegment]]:
    merged: list[TranscriptSegment] = []
    buf: TranscriptSegment | None = None
    for s in segments:
        if buf and buf.speaker_name == s.speaker_name and len(buf.text) < 400:
            buf.text = buf.text + s.text
            buf.end_ms = s.end_ms
        else:
            if buf:
                merged.append(buf)
            buf = s
    if buf:
        merged.append(buf)
    chunks: list[list[TranscriptSegment]] = []
    cur: list[TranscriptSegment] = []
    n = 0
    for s in merged:
        if n + len(s.text) > max_chars and cur:
            chunks.append(cur)
            keep = []
            k = 0
            for x in reversed(cur):
                keep.insert(0, x)
                k += len(x.text)
                if k >= overlap:
                    break
            cur = keep
            n = sum(len(x.text) for x in cur)
        cur.append(s)
        n += len(s.text)
    if cur:
        chunks.append(cur)
    return chunks or [merged]


def _fmt_chunk(segs: list[TranscriptSegment]) -> str:
    lines = []
    for s in segs:
        sp = s.speaker_name or "发言人"
        lines.append(f"[{s.id}] {sp}: {s.text}")
    return "\n".join(lines)


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def entity_summary(ent: Entity | Candidate) -> str:
    if isinstance(ent, Entity):
        p = ent.payload or {}
        t = ent.type
    else:
        p = ent.payload or {}
        t = ent.type
    if t == "decision":
        return f"决策：{p.get('conclusion','')} 依据：{p.get('rationale','')}"
    if t == "commitment":
        return f"承诺：{p.get('item','')} 责任人：{p.get('owner','')}"
    return f"风险：{p.get('description','')}"


async def _link_topic(db: AsyncSession, meeting: Meeting, item: Candidate, vec: list[float] | None) -> int | None:
    if not meeting.space_id:
        return None
    topics = (await db.execute(select(Topic).where(Topic.space_id == meeting.space_id, Topic.merged_into.is_(None)))).scalars().all()
    best = None
    best_s = 0.0
    if vec:
        for t in topics:
            if t.embedding:
                s = _cosine(vec, list(t.embedding))
                if s > best_s:
                    best_s, best = s, t
    if best and best_s >= 0.70:
        return best.id
    name = await gateway.complete(
        task="topic_naming",
        system="为会议实体生成不超过12字的议题名称，只输出名称。",
        user=entity_summary(item),
        db=db,
    )
    name = (name or "未命名议题").strip().splitlines()[0][:40]
    topic = Topic(space_id=meeting.space_id, name=name, summary=entity_summary(item)[:200], embedding=vec)
    db.add(topic)
    await db.flush()
    return topic.id


async def run_extraction(db: AsyncSession, meeting_id: int) -> None:
    meeting = await db.get(Meeting, meeting_id)
    if not meeting or not meeting.space_id:
        return
    meeting.status = "extracting"
    await db.commit()
    try:
        segs = (
            await db.execute(
                select(TranscriptSegment).where(TranscriptSegment.meeting_id == meeting_id).order_by(TranscriptSegment.seq)
            )
        ).scalars().all()
        if not segs:
            meeting.status = "failed"
            await db.commit()
            return
        from app.db.models import EntityMention, EntityRevision

        await db.execute(delete(EntityMention).where(EntityMention.meeting_id == meeting_id))
        ent_ids = (await db.execute(select(Entity.id).where(Entity.meeting_id == meeting_id))).scalars().all()
        if ent_ids:
            await db.execute(delete(EntityRevision).where(EntityRevision.entity_id.in_(ent_ids)))
        await db.execute(delete(Entity).where(Entity.meeting_id == meeting_id))
        await db.flush()
        texts = [s.text for s in segs]
        try:
            vecs = await gateway.embed(texts, db=db)
        except Exception as exc:
            print("segment embed skipped:", exc)
            vecs = []
        for s, v in zip(segs, vecs):
            s.embedding = v
        await db.flush()
        seg_map = {s.id: s for s in segs}
        artifacts = (await db.execute(select(PlatformArtifact).where(PlatformArtifact.meeting_id == meeting_id))).scalars().all()
        try:
            from app.services.summary import ensure_meeting_summary

            artifacts = await ensure_meeting_summary(db, meeting, segs, list(artifacts))
        except Exception as exc:
            print("meeting summary skipped:", exc)
        art_txt = "\n".join(f"[{a.kind}]\n{a.content or ''}" for a in artifacts)[:6000]
        sys1 = prompt_text("extract_pass1.md")
        candidates: list[Candidate] = []
        for chunk in chunk_segments(segs):
            user = f"会议：{meeting.title}\n时间：{meeting.held_at}\n\n逐字稿（行首为 seg_id）：\n{_fmt_chunk(chunk)}"
            out = await gateway.extract(task="extract_pass1", schema=ExtractOut, system=sys1, user=user, db=db, meeting_id=meeting_id)
            candidates.extend(out.items)
        sys2 = prompt_text("extract_pass2.md")
        user2 = "Pass1 候选：\n" + ExtractOut(items=candidates).model_dump_json()
        if art_txt:
            user2 += "\n\n平台纪要参考：\n" + art_txt
        merged = await gateway.extract(task="extract_pass2", schema=ExtractOut, system=sys2, user=user2, db=db, meeting_id=meeting_id)
        meeting.extraction_version = (meeting.extraction_version or 0) + 1
        kept = 0
        summaries = []
        for item in merged.items:
            if item.confidence < 0.5:
                continue
            anchors = validate_anchors(item, seg_map)
            if not anchors:
                continue
            summaries.append(entity_summary(item))
            vec = None
            try:
                vecs2 = await gateway.embed([entity_summary(item)], db=db)
                vec = vecs2[0] if vecs2 else None
            except Exception:
                vec = None
            topic_id = await _link_topic(db, meeting, item, vec)
            db.add(
                Entity(
                    meeting_id=meeting.id,
                    space_id=meeting.space_id,
                    topic_id=topic_id,
                    type=item.type,
                    payload=item.payload,
                    anchor_segment_ids=anchors,
                    status="ai_extracted",
                    extraction_version=meeting.extraction_version,
                    confidence=item.confidence,
                )
            )
            kept += 1
        user = await get_default_user(db)
        deadline = datetime.now(timezone.utc) + timedelta(minutes=settings.confirm_timeout_minutes)
        existing = (
            await db.execute(select(ConfirmationTask).where(ConfirmationTask.meeting_id == meeting.id))
        ).scalar_one_or_none()
        if existing:
            existing.status = "pending"
            existing.deadline_at = deadline
            existing.confirmer_user_id = meeting.space_id and user.id or user.id
        else:
            db.add(
                ConfirmationTask(
                    meeting_id=meeting.id,
                    confirmer_user_id=user.id,
                    deadline_at=deadline,
                    status="pending",
                )
            )
        meeting.status = "confirming" if kept else "done"
        if not kept:
            meeting.status = "done"
        await db.commit()
        from app.services.notify import notify_confirm_task
        from app.services.mentions import scan_mentions

        await scan_mentions(db, meeting.id)
        if kept:
            await notify_confirm_task(meeting, kept)
    except Exception as e:
        meeting.status = "failed"
        await db.commit()
        from app.services.notify import notify_pull_fail

        await notify_pull_fail(f"抽取失败 meeting={meeting_id}: {e}")
        raise
