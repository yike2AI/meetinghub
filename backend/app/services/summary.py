from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Meeting, PlatformArtifact, TranscriptSegment
from app.gateway import gateway, prompt_text

PLATFORM_KINDS = {"platform_summary", "platform_todo", "platform_chapter"}


class TodoItem(BaseModel):
    item: str
    owner: str | None = None


class MeetingSummaryOut(BaseModel):
    outline: list[str] = Field(default_factory=list)
    conclusions: list[str] = Field(default_factory=list)
    todos: list[TodoItem] = Field(default_factory=list)


def has_platform_ai(artifacts: list[PlatformArtifact]) -> bool:
    return any(a.kind in PLATFORM_KINDS and (a.content or "").strip() for a in artifacts)


def compact_transcript(segs: list[TranscriptSegment], max_chars: int = 24000) -> str:
    lines = []
    for s in segs:
        sp = s.speaker_name or ""
        prefix = f"[{s.id}] {sp}: " if sp else f"[{s.id}] "
        lines.append(prefix + (s.text or ""))
    text = "\n".join(lines)
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    return text[:half] + "\n…(中间省略)…\n" + text[-half:]


def format_generated(out: MeetingSummaryOut) -> str:
    parts = ["## 要点大纲"]
    parts.extend(f"- {x}" for x in out.outline) if out.outline else parts.append("- （无）")
    parts.append("\n## 结论")
    parts.extend(f"- {x}" for x in out.conclusions) if out.conclusions else parts.append("- （无）")
    parts.append("\n## 待办")
    if out.todos:
        for t in out.todos:
            owner = f"（{t.owner}）" if t.owner else ""
            parts.append(f"- {t.item}{owner}")
    else:
        parts.append("- （无）")
    return "\n".join(parts)


def _as_text(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, str):
        return val.strip()
    if isinstance(val, list):
        lines: list[str] = []
        for i, it in enumerate(val, 1):
            if isinstance(it, str):
                lines.append(f"{i}. {it}")
            elif isinstance(it, dict):
                title = (
                    it.get("title")
                    or it.get("text")
                    or it.get("content")
                    or it.get("name")
                    or it.get("todo")
                    or it.get("item")
                    or it.get("task")
                )
                extra = it.get("assignee") or it.get("owner") or it.get("speaker") or it.get("user")
                body = it.get("summary") or it.get("description") or it.get("detail")
                bit = str(title) if title else json.dumps(it, ensure_ascii=False)
                if extra:
                    bit = f"{bit}（{extra}）"
                if body and str(body) != str(title):
                    bit = f"{bit}\n{body}"
                lines.append(f"{i}. {bit}")
            else:
                lines.append(f"{i}. {it}")
        return "\n".join(lines)
    if isinstance(val, dict):
        for k in ("markdown", "text", "content", "summary"):
            v = val.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
            if v is not None and k != "markdown":
                inner = _as_text(v)
                if inner:
                    return inner
        return json.dumps(val, ensure_ascii=False, indent=2)
    return str(val)


def _find_artifacts_blob(meta: Any) -> dict[str, Any]:
    if isinstance(meta, list):
        for item in meta:
            found = _find_artifacts_blob(item)
            if found:
                return found
        return {}
    if not isinstance(meta, dict):
        return {}
    data = meta.get("data") if isinstance(meta.get("data"), dict) else meta
    arts = meta.get("artifacts") if isinstance(meta.get("artifacts"), dict) else {}
    blob = {
        "summary": data.get("summary") or arts.get("summary"),
        "todos": data.get("minute_todos") or data.get("todos") or data.get("todo") or arts.get("todos"),
        "chapters": data.get("minute_chapters") or data.get("chapters") or data.get("chapter") or arts.get("chapters"),
        "keywords": data.get("keywords") or arts.get("keywords"),
    }
    if any(blob.get(k) for k in ("summary", "todos", "chapters")):
        return blob
    for key in ("notes", "result"):
        found = _find_artifacts_blob(meta.get(key))
        if found:
            return found
    return blob if any(blob.values()) else {}


def artifacts_from_notes(meta: Any, *, provider: str) -> list[dict[str, Any]]:
    blob = _find_artifacts_blob(meta)
    out: list[dict[str, Any]] = []
    mapping = (
        ("summary", "platform_summary"),
        ("todos", "platform_todo"),
        ("todo", "platform_todo"),
        ("chapters", "platform_chapter"),
        ("chapter", "platform_chapter"),
    )
    seen: set[str] = set()
    for src, kind in mapping:
        if kind in seen:
            continue
        text = _as_text(blob.get(src))
        if not text:
            continue
        seen.add(kind)
        out.append(
            {
                "kind": kind,
                "content": text[:20000],
                "raw": {"provider": provider, "field": src, "payload": blob.get(src)},
            }
        )
    return out


async def ensure_meeting_summary(
    db: AsyncSession,
    meeting: Meeting,
    segs: list[TranscriptSegment],
    artifacts: list[PlatformArtifact],
) -> list[PlatformArtifact]:
    if has_platform_ai(artifacts):
        return artifacts
    await db.execute(
        delete(PlatformArtifact).where(
            PlatformArtifact.meeting_id == meeting.id,
            PlatformArtifact.kind == "generated_summary",
        )
    )
    sys_p = prompt_text("meeting_summary.md")
    user = f"会议：{meeting.title}\n时间：{meeting.held_at}\n\n逐字稿：\n{compact_transcript(segs)}"
    out = await gateway.extract(
        task="meeting_summary",
        schema=MeetingSummaryOut,
        system=sys_p,
        user=user,
        db=db,
        meeting_id=meeting.id,
    )
    row = PlatformArtifact(
        meeting_id=meeting.id,
        kind="generated_summary",
        content=format_generated(out),
        raw={"provider": "model_fallback", "payload": out.model_dump()},
    )
    db.add(row)
    await db.flush()
    return (
        await db.execute(select(PlatformArtifact).where(PlatformArtifact.meeting_id == meeting.id))
    ).scalars().all()
