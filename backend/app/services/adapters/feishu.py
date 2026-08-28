from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings

MINUTE_RE = re.compile(r"/minutes/([A-Za-z0-9]{20,})")


def extract_minute_token(url: str) -> str:
    m = MINUTE_RE.search(url)
    if m:
        return m.group(1)
    token = url.strip().split("?")[0].rstrip("/").split("/")[-1]
    if len(token) >= 20:
        return token
    raise ValueError("无法从链接提取妙记 token")


def _lark_bin() -> str:
    if os.name == "nt":
        return shutil.which("lark-cli.cmd") or shutil.which("lark-cli") or "lark-cli.cmd"
    return shutil.which("lark-cli") or "lark-cli"


async def _run_lark(args: list[str], timeout: float = 180) -> tuple[int, str, str]:
    bin_path = _lark_bin()
    proc = await asyncio.create_subprocess_exec(
        bin_path,
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(settings.data_dir.parent),
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout)
    except TimeoutError:
        proc.kill()
        raise RuntimeError("lark-cli 超时（180s）")
    stdout = out.decode("utf-8", errors="ignore")
    stderr = err.decode("utf-8", errors="ignore")
    if proc.returncode != 0 and ("auth login" in stderr.lower() or "token" in stderr.lower() and "expir" in stderr.lower()):
        raise RuntimeError("飞书个人授权已过期，请运行 lark-cli auth login 重新授权")
    return proc.returncode or 0, stdout, stderr


def _parse_jsonish(stdout: str) -> Any:
    text = stdout.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        start_arr = text.find("[")
        idx = min([i for i in (start, start_arr) if i >= 0], default=-1)
        if idx < 0:
            return None
        return json.loads(text[idx:])


async def search_minutes(*, keyword: str = "", since: str = "") -> list[dict[str, Any]]:
    args = ["minutes", "+search", "--owner-ids", "me", "--as", "user", "--format", "json", "--page-size", "50"]
    if keyword:
        args += ["--query", keyword]
    if since:
        args += ["--start", since]
    code, out, err = await _run_lark(args)
    if code != 0:
        raise RuntimeError(err or out or "lark-cli minutes +search 失败")
    data = _parse_jsonish(out) or {}
    if isinstance(data, list):
        return data
    for key in ("data", "minutes", "items", "list"):
        if isinstance(data.get(key) if isinstance(data, dict) else None, list):
            return data[key]
    if isinstance(data, dict) and "minute" in json.dumps(data, ensure_ascii=False)[:200].lower():
        inner = data.get("data") or data
        if isinstance(inner, dict):
            for v in inner.values():
                if isinstance(v, list):
                    return v
    return []


def _collect_transcript_files(folder: Path) -> list[Path]:
    files = []
    for p in folder.rglob("*"):
        if p.is_file() and p.suffix.lower() in {".txt", ".srt", ".vtt", ".md"}:
            files.append(p)
    return files


async def export_minute(token: str) -> dict[str, Any]:
    out_dir = settings.data_dir / "tmp" / f"feishu_{token}"
    out_dir.mkdir(parents=True, exist_ok=True)
    rel = f"data/tmp/feishu_{token}"
    args = [
        "vc",
        "+notes",
        "--minute-tokens",
        token,
        "--output-dir",
        rel,
        "--overwrite",
        "--as",
        "user",
        "--format",
        "json",
    ]
    code, out, err = await _run_lark(args)
    if code != 0:
        raise RuntimeError(err or out or "lark-cli vc +notes 失败")
    notes_path = out_dir / "notes.json"
    notes_path.write_text(out or "", encoding="utf-8")
    from app.services.parsers import parse_path, parse_txt
    from app.services.summary import artifacts_from_notes

    files = _collect_transcript_files(out_dir)
    segs: list[dict[str, Any]] = []
    for f in files:
        parsed = parse_path(f)
        if parsed:
            segs = parsed
            break
    meta = _parse_jsonish(out) or {}
    title = token
    for p in out_dir.iterdir() if out_dir.exists() else []:
        name = p.name
        if name.startswith("artifact-") and token in name:
            mid = name.removeprefix("artifact-").removesuffix(f"-{token}")
            if mid:
                title = mid
                break
    held_at = datetime.now(timezone.utc)
    artifacts: list[dict[str, Any]] = []
    if isinstance(meta, dict) or isinstance(meta, list):
        title = _pick_title(meta, title)
        held_at = _pick_held_at(meta, held_at)
        artifacts = artifacts_from_notes(meta, provider="feishu")
    if not segs:
        segs = parse_txt("（该妙记暂无逐字稿文件，请稍后重试或改用人工导入）")
    try:
        art_meta = await _fetch_minute_artifacts(token)
        extra = artifacts_from_notes(art_meta, provider="feishu")
        kinds = {a["kind"] for a in artifacts}
        for a in extra:
            if a["kind"] not in kinds:
                artifacts.append(a)
                kinds.add(a["kind"])
        title = _pick_title(art_meta, title)
        held_at = _pick_held_at(art_meta, held_at)
    except Exception as exc:
        print("feishu artifacts api skipped:", exc)
    try:
        info = await _fetch_minute_info(token)
        title = _pick_title(info, title)
        held_at = _pick_held_at(info, held_at)
    except Exception as exc:
        print("feishu minute get skipped:", exc)
    return {
        "platform": "feishu",
        "source_ref": {"minute_token": token},
        "title": title if isinstance(title, str) else str(title),
        "held_at": held_at,
        "participants": [],
        "segments": segs,
        "artifacts": artifacts,
        "raw_files": [{"filename": f.name, "path": str(f)} for f in files],
    }


def _walk_dicts(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk_dicts(v)
    elif isinstance(obj, list):
        for it in obj:
            yield from _walk_dicts(it)


def _pick_title(meta: Any, fallback: str) -> str:
    candidates: list[dict[str, Any]] = []
    if isinstance(meta, dict):
        candidates.append(meta)
        n = meta.get("notes") or meta.get("data")
        if isinstance(n, dict):
            candidates.append(n)
        elif isinstance(n, list) and n and isinstance(n[0], dict):
            candidates.append(n[0])
    for d in candidates:
        val = d.get("title") or d.get("topic")
        if isinstance(val, str) and 0 < len(val.strip()) < 80:
            return val.strip()
    return fallback


def _pick_held_at(meta: Any, fallback: datetime) -> datetime:
    for d in _walk_dicts(meta):
        for key in ("start_time", "create_time", "held_at", "begin_time"):
            val = d.get(key)
            if not val:
                continue
            try:
                if isinstance(val, (int, float)):
                    ts = float(val)
                    if ts > 10_000_000_000:
                        ts /= 1000
                    return datetime.fromtimestamp(ts, tz=timezone.utc)
                text = str(val).replace("Z", "+00:00")
                dt = datetime.fromisoformat(text)
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError, OSError):
                continue
    return fallback


async def _fetch_minute_artifacts(token: str) -> Any:
    code, out, err = await _run_lark(
        ["api", "GET", f"/open-apis/minutes/v1/minutes/{token}/artifacts", "--as", "user", "--format", "json"],
        timeout=60,
    )
    if code != 0:
        raise RuntimeError(err or out or "minutes artifacts 失败")
    return _parse_jsonish(out) or {}


async def _fetch_minute_info(token: str) -> Any:
    code, out, err = await _run_lark(
        ["minutes", "minutes", "get", "--params", json.dumps({"minute_token": token}), "--as", "user", "--format", "json"],
        timeout=30,
    )
    if code != 0:
        raise RuntimeError(err or out or "minutes get 失败")
    return _parse_jsonish(out) or {}


async def pull_from_url(url: str) -> dict[str, Any]:
    return await export_minute(extract_minute_token(url))
