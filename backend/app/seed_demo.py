"""Seed POC space and import sample strategy meetings."""
import asyncio
from pathlib import Path

from app.db.bootstrap import get_default_user
from app.db.models import Space
from app.db.session import SessionLocal
from app.services.importing import import_single
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "data" / "samples"


async def main() -> None:
    async with SessionLocal() as db:
        await get_default_user(db)
        space = (await db.execute(select(Space).where(Space.name == "战略会空间"))).scalar_one_or_none()
        if not space:
            space = Space(
                name="战略会空间",
                security_level="exec",
                confirmer_user_id=1,
                match_rules=[{"type": "feishu_owner_sync", "keyword": "", "since": "2026-01-01"}],
                report_enabled=True,
            )
            db.add(space)
            await db.commit()
            await db.refresh(space)
        sid = space.id
    files = [
        ("2026-06-strategy.srt", "6月月度战略会", "2026-06-03T14:00:00+08:00", "张总,李华,王敏,赵强"),
        ("2026-07-strategy.srt", "7月月度战略会", "2026-07-08T14:00:00+08:00", "张总,李华,王敏,赵强"),
        ("2026-08-strategy.srt", "8月月度战略会", "2026-08-05T14:00:00+08:00", "张总,李华,王敏,赵强"),
    ]
    for name, title, held, people in files:
        path = SAMPLES / name
        await import_single(
            space_id=sid,
            title=title,
            held_at=held,
            participants=people,
            filename=name,
            data=path.read_bytes(),
            extract=True,
        )
        print("imported", title)


if __name__ == "__main__":
    asyncio.run(main())
