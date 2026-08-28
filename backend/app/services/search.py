from __future__ import annotations

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Entity, Meeting, TranscriptSegment
from app.gateway import gateway
from app.services.fts import tokenize


def _rrf(rank: int, k: int = 60) -> float:
    return 1.0 / (k + rank)


async def hybrid_search(db: AsyncSession, q: str, space_id: int | None = None, limit: int = 20) -> list[dict]:
    q = (q or "").strip()
    if not q:
        return []
    tokens = tokenize(q)
    vecs = await gateway.embed([q], db=db)
    vec = vecs[0] if vecs else None
    fts_sql = """
        SELECT id, meeting_id, seq, speaker_name, start_ms, text,
               ts_rank(search_vector, plainto_tsquery('simple', :tok)) AS rank
        FROM transcript_segment
        WHERE search_vector @@ plainto_tsquery('simple', :tok)
        ORDER BY rank DESC
        LIMIT 50
    """
    fts_rows = (await db.execute(text(fts_sql), {"tok": tokens})).mappings().all()
    vec_rows = []
    if vec:
        vec_sql = """
            SELECT id, meeting_id, seq, speaker_name, start_ms, text,
                   1 - (embedding <=> CAST(:emb AS vector)) AS sim
            FROM transcript_segment
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:emb AS vector)
            LIMIT 50
        """
        vec_rows = (await db.execute(text(vec_sql), {"emb": str(vec)})).mappings().all()
    scores: dict[int, float] = {}
    payload: dict[int, dict] = {}
    for i, row in enumerate(fts_rows, 1):
        scores[row["id"]] = scores.get(row["id"], 0) + _rrf(i)
        payload[row["id"]] = dict(row)
    for i, row in enumerate(vec_rows, 1):
        scores[row["id"]] = scores.get(row["id"], 0) + _rrf(i)
        payload[row["id"]] = dict(row)
    ilike_rows = (
        await db.execute(
            select(TranscriptSegment).where(TranscriptSegment.text.ilike(f"%{q}%")).limit(30)
        )
    ).scalars().all()
    for i, s in enumerate(ilike_rows, 1):
        scores[s.id] = scores.get(s.id, 0) + _rrf(i + 10)
        payload[s.id] = {
            "id": s.id,
            "meeting_id": s.meeting_id,
            "seq": s.seq,
            "speaker_name": s.speaker_name,
            "start_ms": s.start_ms,
            "text": s.text,
        }
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    out = []
    for sid, sc in ranked[:limit]:
        row = payload[sid]
        m = await db.get(Meeting, row["meeting_id"])
        if space_id and m and m.space_id != space_id:
            continue
        snippet = row["text"]
        idx = snippet.find(q)
        if idx >= 0:
            snippet = snippet[max(0, idx - 24) : idx + len(q) + 40]
        out.append(
            {
                "kind": "segment",
                "segment_id": sid,
                "meeting_id": row["meeting_id"],
                "meeting_title": m.title if m else "",
                "held_at": m.held_at.isoformat() if m else None,
                "speaker_name": row.get("speaker_name"),
                "seq": row.get("seq"),
                "snippet": snippet,
                "score": round(sc, 4),
            }
        )
    ents = (
        await db.execute(select(Entity).where(Entity.status != "deleted").limit(200))
    ).scalars().all()
    ql = q.lower()
    for e in ents:
        blob = (str(e.payload) + " " + e.type).lower()
        if ql in blob and (not space_id or e.space_id == space_id):
            out.append(
                {
                    "kind": "entity",
                    "entity_id": e.id,
                    "type": e.type,
                    "payload": e.payload,
                    "meeting_id": e.meeting_id,
                    "anchor_segment_ids": e.anchor_segment_ids,
                    "score": 0.5,
                }
            )
    return out[:limit]
