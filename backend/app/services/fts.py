from __future__ import annotations

import jieba
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def tokenize(text_in: str) -> str:
    return " ".join(w.strip() for w in jieba.cut_for_search(text_in or "") if w.strip())


async def set_search_vector(db: AsyncSession, segment_id: int, raw_text: str) -> None:
    tokens = tokenize(raw_text)
    await db.execute(
        text("UPDATE transcript_segment SET search_vector = to_tsvector('simple', :tok) WHERE id = :id"),
        {"tok": tokens, "id": segment_id},
    )
