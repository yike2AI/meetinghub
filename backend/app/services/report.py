from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Entity, Meeting, Report, Space
from app.gateway import gateway
from app.services.notify import notify_report_ready


def _row(e: Entity) -> str:
    p = e.payload or {}
    mark = "（AI 自动入库）" if e.auto_committed else ""
    if e.type == "decision":
        return f"| {p.get('conclusion','')} | {p.get('decider') or '-'} | {p.get('rationale') or '-'} | entity:{e.id}{mark} |"
    if e.type == "commitment":
        return f"| {p.get('item','')} | {p.get('owner') or '-'} | {p.get('due_date') or '-'} | entity:{e.id}{mark} |"
    return f"| {p.get('description','')} | {p.get('raiser') or '-'} | {p.get('impact') or '-'} | entity:{e.id}{mark} |"


async def generate_report(db: AsyncSession, space_id: int, period_label: str | None = None) -> Report:
    space = await db.get(Space, space_id)
    if not space:
        raise ValueError("空间不存在")
    now = datetime.now(timezone.utc)
    period = period_label or now.strftime("%Y-%m")
    meetings = (
        await db.execute(
            select(Meeting).where(Meeting.space_id == space_id, Meeting.archived.is_(False)).order_by(Meeting.held_at.desc())
        )
    ).scalars().all()
    mids = [m.id for m in meetings]
    ents = (
        await db.execute(
            select(Entity).where(Entity.space_id == space_id, Entity.status.in_(["confirmed", "auto_committed", "ai_extracted"]))
        )
    ).scalars().all()
    decisions = [e for e in ents if e.type == "decision"]
    commits = [e for e in ents if e.type == "commitment"]
    risks = [e for e in ents if e.type == "risk"]
    prev = (
        await db.execute(select(Report).where(Report.space_id == space_id).order_by(Report.created_at.desc()))
    ).scalars().first()
    compare = "本期为该空间首份报告。"
    if prev:
        compare = await gateway.complete(
            task="report_compare",
            system="根据上期报告与本期实体，写「上期议题本期进展」对照，每段末尾附 entity id。中文 Markdown。",
            user=f"上期报告：\n{prev.content_md[:6000]}\n\n本期实体：\n{[{'id': e.id, 'type': e.type, 'payload': e.payload} for e in ents][:80]}",
            db=db,
        )
    overview = "\n".join(f"- {m.held_at.strftime('%Y-%m-%d')} {m.title}（{m.status}）" for m in meetings[:20]) or "- 暂无会议"
    md = f"""# {space.name}复盘报告（{period}）

## 一、会议概览

{overview}

## 二、决策清单

| 结论 | 拍板人 | 依据 | 溯源 |
| --- | --- | --- | --- |
{chr(10).join(_row(e) for e in decisions) or '| 暂无 | - | - | - |'}

## 三、承诺清单

| 事项 | 责任人 | 期限 | 溯源 |
| --- | --- | --- | --- |
{chr(10).join(_row(e) for e in commits) or '| 暂无 | - | - | - |'}

## 四、风险清单

| 描述 | 提出人 | 影响 | 溯源 |
| --- | --- | --- | --- |
{chr(10).join(_row(e) for e in risks) or '| 暂无 | - | - | - |'}

## 五、上期议题进展对照

{compare}

## 附录：实体引用索引

{chr(10).join(f"- entity:{e.id} · {e.type} · meeting:{e.meeting_id}" for e in ents) or '- 无'}
"""
    report = Report(space_id=space_id, period_label=period, meeting_ids=mids or [0], content_md=md, status="draft")
    db.add(report)
    await db.commit()
    await db.refresh(report)
    await notify_report_ready(f"{space.name} {period}", report.id)
    return report
