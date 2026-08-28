from __future__ import annotations

import binascii
import re
from typing import Any

import httpx

from app.config import settings

SHANJI_RE = re.compile(r"shanji\.dingtalk\.com/app/transcribes/([A-Za-z0-9_]+)", re.I)


def parse_dingtalk_ref(raw: str) -> str:
    """Accept conferenceId, or a shanji.dingtalk.com 听记 URL."""
    text = (raw or "").strip()
    m = SHANJI_RE.search(text)
    if m:
        token = m.group(1)
        try:
            decoded = binascii.unhexlify(token).decode("utf-8", errors="ignore")
        except (binascii.Error, ValueError):
            decoded = ""
        # v2uid{xxx}_{conferenceOrBizId}_{n} seen in 听记分享链接
        if decoded.startswith("v2uid") and "_" in decoded:
            parts = decoded.split("_")
            if len(parts) >= 2 and parts[1]:
                return parts[1]
        return token
    return text.rstrip("/").split("/")[-1].split("?")[0]


def enabled() -> bool:
    return bool(settings.dingtalk_app_key and settings.dingtalk_app_secret)


async def _access_token() -> str:
    url = "https://api.dingtalk.com/v1.0/oauth2/accessToken"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            url,
            json={"appKey": settings.dingtalk_app_key, "appSecret": settings.dingtalk_app_secret},
        )
        r.raise_for_status()
        data = r.json()
        token = data.get("accessToken") or data.get("access_token")
        if not token:
            raise RuntimeError(f"钉钉 token 失败: {data}")
        return token


async def pull_texts(conference_id: str) -> dict[str, Any]:
    if not enabled():
        raise RuntimeError("钉钉企业应用未配置（DINGTALK_APP_KEY / APP_SECRET）")
    token = await _access_token()
    segs: list[dict[str, Any]] = []
    next_token = None
    seq = 1
    async with httpx.AsyncClient(timeout=60) as client:
        while True:
            url = f"https://api.dingtalk.com/v1.0/conference/videoConferences/{conference_id}/cloudRecords/getTexts"
            params = {"maxResults": 2000}
            if next_token:
                params["nextToken"] = next_token
            r = await client.get(url, params=params, headers={"x-acs-dingtalk-access-token": token})
            if r.status_code >= 400:
                raise RuntimeError(f"钉钉听记拉取失败: {r.text}")
            data = r.json()
            items = data.get("paragraphList") or data.get("result") or data.get("texts") or []
            if isinstance(items, dict):
                items = items.get("paragraphList") or []
            for it in items:
                text = it.get("text") or it.get("content") or ""
                if not text:
                    continue
                segs.append(
                    {
                        "seq": seq,
                        "speaker_name": it.get("nick") or it.get("speaker") or it.get("speakerName"),
                        "speaker_platform_id": it.get("unionId") or it.get("openId"),
                        "start_ms": it.get("startTime") or it.get("start_ms"),
                        "end_ms": it.get("endTime") or it.get("end_ms"),
                        "text": text,
                    }
                )
                seq += 1
            next_token = data.get("nextToken")
            if not next_token:
                break
    if not segs:
        return {
            "platform": "dingtalk",
            "source_ref": {"conferenceId": conference_id},
            "title": f"钉钉会议 {conference_id}",
            "held_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            "participants": [],
            "segments": [],
            "artifacts": [],
            "raw_files": [],
            "empty": True,
        }
    from datetime import datetime, timezone

    return {
        "platform": "dingtalk",
        "source_ref": {"conferenceId": conference_id},
        "title": f"钉钉会议 {conference_id}",
        "held_at": datetime.now(timezone.utc),
        "participants": [],
        "segments": segs,
        "artifacts": [],
        "raw_files": [],
    }
