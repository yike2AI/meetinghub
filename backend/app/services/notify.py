from __future__ import annotations

import hashlib
import hmac
import time
import urllib.parse

import httpx

from app.config import settings


async def send_markdown(title: str, text: str) -> None:
    if not settings.dingtalk_webhook:
        return
    url = settings.dingtalk_webhook
    if settings.dingtalk_secret:
        ts = str(round(time.time() * 1000))
        secret_enc = settings.dingtalk_secret.encode("utf-8")
        string_to_sign = f"{ts}\n{settings.dingtalk_secret}"
        sign = urllib.parse.quote_plus(
            hmac.new(secret_enc, string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
        )
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}timestamp={ts}&sign={sign}"
    body = {"msgtype": "markdown", "markdown": {"title": title, "text": text}}
    last = None
    for _ in range(3):
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(url, json=body)
                r.raise_for_status()
                return
        except Exception as e:
            last = e
    if last:
        print("dingtalk notify failed", last)


async def notify_confirm_task(meeting, count: int) -> None:
    link = f"{settings.frontend_url}/meetings/{meeting.id}/confirm"
    await send_markdown(
        "待确认抽取结果",
        f"### 会议「{meeting.title}」抽取完成\n\n共 {count} 条实体待确认\n\n[打开确认页]({link})",
    )


async def notify_report_ready(title: str, report_id: int) -> None:
    link = f"{settings.frontend_url}/reports/{report_id}"
    await send_markdown("复盘报告已就绪", f"### {title}\n\n[查看报告]({link})")


async def notify_pull_fail(message: str) -> None:
    await send_markdown("会议拉取/抽取失败", f"### 告警\n\n{message}")
