from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path
from typing import Any

from docx import Document
from pypdf import PdfReader

TS_RE = re.compile(r"(?:(\d{1,2}):)?(\d{1,2}):(\d{2})(?:[.,](\d{1,3}))?")


def _ts_to_ms(raw: str) -> int | None:
    m = TS_RE.search(raw or "")
    if not m:
        return None
    h = int(m.group(1) or 0)
    mi = int(m.group(2))
    s = int(m.group(3))
    ms = int((m.group(4) or "0").ljust(3, "0")[:3])
    return ((h * 60 + mi) * 60 + s) * 1000 + ms


def parse_srt(text: str) -> list[dict[str, Any]]:
    blocks = re.split(r"\n\s*\n", text.strip())
    segs: list[dict[str, Any]] = []
    seq = 1
    for block in blocks:
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        if lines[0].isdigit():
            lines = lines[1:]
        start_ms = end_ms = None
        speaker = None
        body_lines = lines
        if lines and "-->" in lines[0]:
            a, b = [p.strip() for p in lines[0].split("-->", 1)]
            start_ms, end_ms = _ts_to_ms(a), _ts_to_ms(b)
            body_lines = lines[1:]
        body = "\n".join(body_lines).strip()
        if not body:
            continue
        sm = re.match(r"^([^:：]{1,20})[:：]\s*(.*)$", body, re.S)
        if sm:
            speaker, body = sm.group(1).strip(), sm.group(2).strip()
        segs.append(
            {
                "seq": seq,
                "speaker_name": speaker,
                "speaker_platform_id": None,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "text": body,
            }
        )
        seq += 1
    return segs


def parse_txt(text: str) -> list[dict[str, Any]]:
    chunks = re.split(r"\n\s*\n", text.strip())
    segs: list[dict[str, Any]] = []
    seq = 1
    speaker_line = re.compile(r"^\[?(?P<spk>[^\]\n]{1,20})\]?\s+(?P<ts>\d{1,2}:\d{2}(?::\d{2})?)\s*$")
    i = 0
    paras = [c.strip() for c in chunks if c.strip()]
    while i < len(paras):
        p = paras[i]
        first = p.split("\n", 1)[0]
        m = speaker_line.match(first)
        speaker = None
        start_ms = None
        body = p
        if m:
            speaker = m.group("spk")
            start_ms = _ts_to_ms(m.group("ts"))
            rest = p.split("\n", 1)
            body = rest[1].strip() if len(rest) > 1 else ""
            if not body and i + 1 < len(paras):
                i += 1
                body = paras[i]
        if body:
            segs.append(
                {
                    "seq": seq,
                    "speaker_name": speaker,
                    "speaker_platform_id": None,
                    "start_ms": start_ms,
                    "end_ms": None,
                    "text": body,
                }
            )
            seq += 1
        i += 1
    if not segs and text.strip():
        for n, line in enumerate([ln.strip() for ln in text.splitlines() if ln.strip()], 1):
            segs.append(
                {
                    "seq": n,
                    "speaker_name": None,
                    "speaker_platform_id": None,
                    "start_ms": None,
                    "end_ms": None,
                    "text": line,
                }
            )
    return segs


def parse_docx_bytes(data: bytes) -> list[dict[str, Any]]:
    doc = Document(BytesIO(data))
    text = "\n\n".join(p.text.strip() for p in doc.paragraphs if p.text.strip())
    return parse_txt(text)


def parse_pdf_bytes(data: bytes) -> list[dict[str, Any]]:
    reader = PdfReader(BytesIO(data))
    parts = [(page.extract_text() or "") for page in reader.pages]
    return parse_txt("\n\n".join(parts))


def parse_file(filename: str, data: bytes) -> list[dict[str, Any]]:
    name = filename.lower()
    if name.endswith(".srt") or name.endswith(".vtt"):
        return parse_srt(data.decode("utf-8", errors="ignore"))
    if name.endswith(".docx"):
        return parse_docx_bytes(data)
    if name.endswith(".pdf"):
        return parse_pdf_bytes(data)
    return parse_txt(data.decode("utf-8", errors="ignore"))


def parse_path(path: Path) -> list[dict[str, Any]]:
    return parse_file(path.name, path.read_bytes())
