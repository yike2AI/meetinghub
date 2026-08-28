from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.tools import TOOLS, dispatch
from app.db.models import ChatMessage, ChatSession, Meeting, TranscriptSegment
from app.gateway import gateway, prompt_text


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def run_ask(db: AsyncSession, session: ChatSession, question: str) -> AsyncIterator[str]:
    history = (
        await db.execute(select(ChatMessage).where(ChatMessage.session_id == session.id).order_by(ChatMessage.id))
    ).scalars().all()
    messages: list[dict] = [{"role": "system", "content": prompt_text("agent_system.md")}]
    messages.append(
        {
            "role": "system",
            "content": f"当前会话范围 space_id={session.space_id} topic_id={session.topic_id} date_from={session.date_from} date_to={session.date_to}",
        }
    )
    for h in history[-12:]:
        messages.append({"role": h.role, "content": h.content_md})
    messages.append({"role": "user", "content": question})

    trace: list[dict] = []
    citations: list[dict] = []
    answer_parts: list[str] = []
    for turn in range(10):
        yield sse("status", {"text": f"思考中（第 {turn + 1} 轮）…"})
        msg = await gateway.chat_tools(task="agent_chat", messages=messages, tools=TOOLS)
        tool_calls = msg.get("tool_calls") or []
        content = msg.get("content") or ""
        if content:
            answer_parts.append(content)
            yield sse("delta", {"text": content})
        if not tool_calls:
            break
        messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})
        for tc in tool_calls:
            fn = tc.get("function") or {}
            name = fn.get("name")
            raw_args = fn.get("arguments") or "{}"
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except json.JSONDecodeError:
                args = {}
            yield sse("status", {"text": f"正在调用 {name}…"})
            try:
                result = await dispatch(db, session.space_id, name, args)
            except Exception as e:
                result = {"error": str(e)}
            trace.append({"tool": name, "args": args, "ok": "error" not in result})
            _collect_citations(result, citations)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.get("id"),
                    "content": json.dumps(result, ensure_ascii=False)[:12000],
                }
            )
    raw_answer = "\n".join(answer_parts).strip() or "资产库中未找到相关记录。"
    citations = await _validate_citations(db, session.space_id, citations, raw_answer)
    for i, c in enumerate(citations, 1):
        yield sse("citation", {"index": i, **c})
    user_msg = ChatMessage(session_id=session.id, role="user", content_md=question, citations=[])
    asst = ChatMessage(
        session_id=session.id,
        role="assistant",
        content_md=raw_answer,
        citations=citations,
        tool_trace=trace,
    )
    db.add(user_msg)
    db.add(asst)
    if not session.title:
        session.title = question[:40]
    await db.commit()
    await db.refresh(asst)
    yield sse("done", {"message_id": asst.id, "suggestions": _suggestions(question)})


def _collect_citations(result: dict, citations: list[dict]) -> None:
    if not isinstance(result, dict):
        return
    for hit in result.get("hits") or []:
        if hit.get("segment_id") and hit.get("meeting_id"):
            citations.append(
                {
                    "meeting_id": hit["meeting_id"],
                    "segment_id": hit["segment_id"],
                    "quote": (hit.get("snippet") or "")[:180],
                }
            )
    for s in result.get("segments") or []:
        if s.get("id") or s.get("segment_id"):
            citations.append(
                {
                    "meeting_id": result.get("meeting", {}).get("id") or s.get("meeting_id"),
                    "segment_id": s.get("id") or s.get("segment_id"),
                    "quote": (s.get("text") or "")[:180],
                }
            )
    for e in result.get("entities") or result.get("commitments") or result.get("risks") or []:
        mids = e.get("meeting_id")
        anchors = e.get("anchor_segment_ids") or []
        if mids and anchors:
            citations.append({"meeting_id": mids, "segment_id": anchors[0], "entity_id": e.get("id") or e.get("entity_id"), "quote": ""})


async def _validate_citations(db: AsyncSession, space_id: int, citations: list[dict], answer: str) -> list[dict]:
    seen = set()
    out = []
    for c in citations:
        sid = c.get("segment_id")
        mid = c.get("meeting_id")
        if not sid or not mid or sid in seen:
            continue
        seg = await db.get(TranscriptSegment, int(sid))
        m = await db.get(Meeting, int(mid))
        if not seg or not m or m.space_id != space_id:
            continue
        seen.add(sid)
        out.append(
            {
                "meeting_id": m.id,
                "meeting_title": m.title,
                "held_at": m.held_at.isoformat(),
                "segment_id": seg.id,
                "quote": c.get("quote") or seg.text[:160],
                "entity_id": c.get("entity_id"),
            }
        )
        if len(out) >= 8:
            break
    extra_ids = [int(x) for x in re.findall(r"seg[_\s-]?id[:\s]*([0-9]+)", answer, flags=re.I)]
    for sid in extra_ids:
        if sid in seen:
            continue
        seg = await db.get(TranscriptSegment, sid)
        if not seg:
            continue
        m = await db.get(Meeting, seg.meeting_id)
        if not m or m.space_id != space_id:
            continue
        seen.add(sid)
        out.append(
            {
                "meeting_id": m.id,
                "meeting_title": m.title,
                "held_at": m.held_at.isoformat(),
                "segment_id": seg.id,
                "quote": seg.text[:160],
            }
        )
    return out


def _suggestions(q: str) -> list[str]:
    return ["当时为什么这么定？", "有哪些承诺后来没了下文？", "相关风险后来怎么说的？"]
