from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.bootstrap import get_default_user
from app.db.models import Meeting, PlatformArtifact, Space, TranscriptSegment
from app.services.fts import set_search_vector

RawMeeting = dict[str, Any]


def match_space(space: Space, raw: RawMeeting) -> bool:
    title = (raw.get("title") or "")
    for rule in space.match_rules or []:
        rtype = rule.get("type")
        if rtype == "title_keyword":
            kw = rule.get("value") or rule.get("keyword") or ""
            if kw and kw in title:
                return True
            if not kw:
                return True
        if rtype == "recurring_meeting_id":
            cid = (raw.get("source_ref") or {}).get("conferenceId")
            if cid and cid == rule.get("value"):
                return True
        if rtype == "feishu_owner_sync":
            kw = rule.get("keyword") or ""
            if not kw or kw in title:
                return True
    return False


async def ingest_raw(db: AsyncSession, raw: RawMeeting, space_id: int | None = None) -> Meeting:
    source = raw["platform"]
    source_ref = raw.get("source_ref") or {}
    existing = (
        await db.execute(select(Meeting).where(Meeting.source == source, Meeting.source_ref == source_ref))
    ).scalar_one_or_none()
    if existing:
        meeting = existing
        meeting.title = raw.get("title") or meeting.title
        if raw.get("held_at"):
            meeting.held_at = raw["held_at"]
        meeting.participants = raw.get("participants") or meeting.participants
        if space_id:
            meeting.space_id = space_id
        await db.execute(delete(TranscriptSegment).where(TranscriptSegment.meeting_id == meeting.id))
        await db.execute(delete(PlatformArtifact).where(PlatformArtifact.meeting_id == meeting.id))
    else:
        if space_id is None:
            spaces = (await db.execute(select(Space).where(Space.archived.is_(False)))).scalars().all()
            for sp in spaces:
                if match_space(sp, raw):
                    space_id = sp.id
                    break
        meeting = Meeting(
            space_id=space_id,
            title=raw.get("title") or "未命名会议",
            held_at=raw["held_at"],
            source=source,
            source_ref=source_ref,
            participants=raw.get("participants") or [],
            status="unclaimed" if space_id is None else "ingested",
        )
        db.add(meeting)
        await db.flush()

    raw_dir = settings.data_dir / "raw" / str(meeting.id)
    raw_dir.mkdir(parents=True, exist_ok=True)
    for f in raw.get("raw_files") or []:
        src = Path(f.get("path") or "")
        if src.exists():
            dest = raw_dir / (f.get("filename") or src.name)
            dest.write_bytes(src.read_bytes())

    for seg in raw.get("segments") or []:
        row = TranscriptSegment(
            meeting_id=meeting.id,
            seq=int(seg["seq"]),
            speaker_name=seg.get("speaker_name"),
            start_ms=seg.get("start_ms"),
            end_ms=seg.get("end_ms"),
            text=seg.get("text") or "",
        )
        db.add(row)
        await db.flush()
        await set_search_vector(db, row.id, row.text)

    for art in raw.get("artifacts") or []:
        db.add(
            PlatformArtifact(
                meeting_id=meeting.id,
                kind=art.get("kind") or "platform_summary",
                content=art.get("content"),
                raw=art.get("raw"),
            )
        )
    if meeting.space_id:
        meeting.status = "ingested"
    await db.commit()
    await db.refresh(meeting)
    return meeting
