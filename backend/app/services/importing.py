from __future__ import annotations

import csv
import io
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Any

from fastapi import UploadFile

from app.config import settings
from app.db.session import SessionLocal
from app.services.ingest import ingest_raw
from app.services.parsers import parse_file


def _held_at(raw: str | None) -> datetime:
    if not raw:
        return datetime.now(timezone.utc)
    raw = raw.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(raw)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)


async def import_single(
    *,
    space_id: int,
    title: str,
    held_at: str | None,
    participants: str | None,
    filename: str,
    data: bytes,
    extract: bool = True,
) -> dict[str, Any]:
    segs = parse_file(filename, data)
    if not segs:
        raise ValueError("未能解析出逐字稿内容")
    tmp = settings.data_dir / "tmp" / f"{uuid.uuid4().hex}_{filename}"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_bytes(data)
    people = [{"name": n.strip()} for n in (participants or "").split(",") if n.strip()]
    raw = {
        "platform": "manual",
        "source_ref": {"import_id": uuid.uuid4().hex, "filename": filename},
        "title": title or filename,
        "held_at": _held_at(held_at),
        "participants": people,
        "segments": segs,
        "artifacts": [],
        "raw_files": [{"filename": filename, "path": str(tmp)}],
    }
    async with SessionLocal() as db:
        meeting = await ingest_raw(db, raw, space_id=space_id)
        mid = meeting.id
    if extract:
        from app.worker import enqueue_extraction

        await enqueue_extraction(mid)
    return {"meeting_id": mid, "segments": len(segs)}


async def import_batch_zip(space_id: int, zip_bytes: bytes) -> dict[str, Any]:
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    names = zf.namelist()
    meta_name = next((n for n in names if n.lower().endswith(".csv") and not n.startswith("__")), None)
    rows: list[dict[str, str]] = []
    if meta_name:
        with zf.open(meta_name) as f:
            text = io.TextIOWrapper(f, encoding="utf-8-sig")
            rows = list(csv.DictReader(text))
    results = []
    for info in zf.infolist():
        if info.is_dir() or info.filename.lower().endswith(".csv"):
            continue
        base = info.filename.split("/")[-1]
        if not base:
            continue
        meta = next((r for r in rows if r.get("filename") == base or r.get("filename") == info.filename), {})
        data = zf.read(info.filename)
        sid = int(meta.get("space_id") or space_id)
        item = await import_single(
            space_id=sid,
            title=meta.get("title") or base,
            held_at=meta.get("held_at"),
            participants=meta.get("participants"),
            filename=base,
            data=data,
            extract=True,
        )
        results.append(item)
    return {"count": len(results), "items": results}


async def import_upload(file: UploadFile, **kwargs) -> dict[str, Any]:
    data = await file.read()
    name = file.filename or "upload.txt"
    if name.lower().endswith(".zip"):
        return await import_batch_zip(int(kwargs["space_id"]), data)
    return await import_single(filename=name, data=data, **kwargs)
