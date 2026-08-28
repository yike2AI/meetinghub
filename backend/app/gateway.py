from __future__ import annotations

import asyncio
import hashlib
import json
import math
from typing import Any

import httpx
import jieba
import yaml
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import ROOT, settings
from app.db.models import LlmUsage

ANTHROPIC_URL = settings.anthropic_base_url.rstrip("/") + "/v1/messages"


def _load_models() -> dict[str, Any]:
    path = settings.models_yaml
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


MODELS = _load_models()


def prompt_text(name: str) -> str:
    p = ROOT / "prompts" / name
    return p.read_text(encoding="utf-8") if p.exists() else ""


def local_embed(texts: list[str], dim: int = 1024) -> list[list[float]]:
    out: list[list[float]] = []
    for t in texts:
        vec = [0.0] * dim
        for w in jieba.cut_for_search(t or ""):
            w = w.strip()
            if not w:
                continue
            h = int(hashlib.md5(w.encode("utf-8")).hexdigest(), 16)
            vec[h % dim] += 1.0
        n = math.sqrt(sum(x * x for x in vec)) or 1.0
        out.append([x / n for x in vec])
    return out


def _openai_tools_to_anthropic(tools: list[dict] | None) -> list[dict]:
    if not tools:
        return []
    converted = []
    for t in tools:
        fn = t.get("function") or t
        converted.append(
            {
                "name": fn["name"],
                "description": fn.get("description") or "",
                "input_schema": fn.get("parameters") or {"type": "object", "properties": {}},
            }
        )
    return converted


def _split_messages(messages: list[dict]) -> tuple[str, list[dict]]:
    system_parts = [m["content"] for m in messages if m.get("role") == "system"]
    system = "\n\n".join(system_parts)
    converted: list[dict] = []
    pending_tools: list[dict] = []
    for m in messages:
        role = m.get("role")
        if role == "system":
            continue
        if role == "tool":
            pending_tools.append(
                {"type": "tool_result", "tool_use_id": m.get("tool_call_id"), "content": m.get("content") or ""}
            )
            continue
        if pending_tools:
            converted.append({"role": "user", "content": pending_tools})
            pending_tools = []
        if role == "assistant" and m.get("tool_calls"):
            blocks: list[dict] = []
            if m.get("content"):
                blocks.append({"type": "text", "text": m["content"]})
            for tc in m["tool_calls"]:
                fn = tc.get("function") or {}
                args = fn.get("arguments") or "{}"
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                blocks.append({"type": "tool_use", "id": tc.get("id"), "name": fn.get("name"), "input": args})
            converted.append({"role": "assistant", "content": blocks})
            continue
        converted.append({"role": role, "content": m.get("content") or ""})
    if pending_tools:
        converted.append({"role": "user", "content": pending_tools})
    return system, converted


def _from_anthropic(msg: dict) -> dict[str, Any]:
    blocks = msg.get("content") or []
    texts = []
    tool_calls = []
    for b in blocks:
        if b.get("type") == "text":
            texts.append(b.get("text") or "")
        elif b.get("type") == "tool_use":
            tool_calls.append(
                {
                    "id": b.get("id"),
                    "type": "function",
                    "function": {"name": b.get("name"), "arguments": json.dumps(b.get("input") or {}, ensure_ascii=False)},
                }
            )
    return {"role": "assistant", "content": "".join(texts), "tool_calls": tool_calls or None}


class ModelGateway:
    def __init__(self) -> None:
        self._cfg = MODELS
        self._embed_remote_ok: bool | None = None

    def _spec(self, task: str) -> dict[str, Any]:
        spec = self._cfg.get(task) or {}
        if not spec:
            spec = {"provider": "zhipu", "model": settings.anthropic_model, "api_key_env": "GLM_API_KEY"}
        return spec

    def _key(self) -> str:
        return settings.glm_api_key or settings.anthropic_auth_token

    async def _chat(
        self,
        *,
        task: str,
        messages: list[dict],
        json_mode: bool = False,
        tools: list[dict] | None = None,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        key = self._key()
        if not key:
            raise RuntimeError("GLM_API_KEY 未配置")
        spec = self._spec(task)
        system, anth_msgs = _split_messages(messages)
        if json_mode:
            system = (system + "\n\n你必须只输出合法 JSON 对象，不要 Markdown 代码块。").strip()
        body: dict[str, Any] = {
            "model": spec.get("model") or settings.anthropic_model,
            "max_tokens": 4096,
            "temperature": temperature,
            "messages": anth_msgs or [{"role": "user", "content": "开始"}],
        }
        if system:
            body["system"] = system
        anth_tools = _openai_tools_to_anthropic(tools)
        if anth_tools:
            body["tools"] = anth_tools
        headers = {
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        async with httpx.AsyncClient(timeout=180) as client:
            last = None
            for attempt in range(5):
                r = await client.post(ANTHROPIC_URL, headers=headers, json=body)
                if r.status_code in {429, 529, 500}:
                    await asyncio.sleep(2 * (attempt + 1))
                    last = r
                    continue
                if r.status_code >= 400:
                    raise RuntimeError(f"模型调用失败 {r.status_code}: {r.text[:500]}")
                data = r.json()
                return {
                    "choices": [{"message": _from_anthropic(data)}],
                    "usage": {
                        "prompt_tokens": (data.get("usage") or {}).get("input_tokens"),
                        "completion_tokens": (data.get("usage") or {}).get("output_tokens"),
                    },
                    "raw": data,
                }
            if last is not None:
                raise RuntimeError(f"模型调用失败 {last.status_code}: {last.text[:500]}")
            raise RuntimeError("模型调用失败")

    async def extract(
        self,
        *,
        task: str,
        schema: type[BaseModel],
        system: str,
        user: str,
        db: AsyncSession | None = None,
        meeting_id: int | None = None,
    ) -> BaseModel:
        last_err = ""
        for _ in range(3):
            extra = f"\n\n上次 JSON 校验失败：{last_err}\n请只输出符合 schema 的 JSON。" if last_err else ""
            data = await self._chat(
                task=task,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user + extra}],
                json_mode=True,
            )
            usage = data.get("usage") or {}
            if db:
                db.add(
                    LlmUsage(
                        task=task,
                        provider="zhipu",
                        model=self._spec(task).get("model", ""),
                        input_tokens=usage.get("prompt_tokens"),
                        output_tokens=usage.get("completion_tokens"),
                        meeting_id=meeting_id,
                    )
                )
            content = (data["choices"][0]["message"].get("content") or "{}").strip()
            if content.startswith("```"):
                content = content.strip("`")
                content = content.split("\n", 1)[-1]
            try:
                obj = json.loads(content)
                return schema.model_validate(obj)
            except (json.JSONDecodeError, ValidationError) as e:
                last_err = str(e)
        raise RuntimeError(f"{task} 结构化输出失败: {last_err}")

    async def complete(self, *, task: str, system: str, user: str, db: AsyncSession | None = None) -> str:
        data = await self._chat(
            task=task,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        )
        if db:
            usage = data.get("usage") or {}
            db.add(
                LlmUsage(
                    task=task,
                    provider="zhipu",
                    model=self._spec(task).get("model", ""),
                    input_tokens=usage.get("prompt_tokens"),
                    output_tokens=usage.get("completion_tokens"),
                )
            )
        return data["choices"][0]["message"].get("content") or ""

    async def chat_tools(self, *, task: str, messages: list[dict], tools: list[dict]) -> dict[str, Any]:
        data = await self._chat(task=task, messages=messages, tools=tools, temperature=0.3)
        msg = data["choices"][0]["message"]
        if not msg.get("tool_calls"):
            msg.pop("tool_calls", None)
        return msg

    async def embed(self, texts: list[str], db: AsyncSession | None = None) -> list[list[float]]:
        if not texts:
            return []
        spec = self._spec("embedding")
        dim = int(spec.get("dimensions") or 1024)
        if self._embed_remote_ok is not False:
            try:
                key = self._key()
                async with httpx.AsyncClient(timeout=30) as client:
                    r = await client.post(
                        "https://open.bigmodel.cn/api/paas/v4/embeddings",
                        headers={"Authorization": f"Bearer {key}"},
                        json={"model": spec.get("model", "embedding-3"), "input": texts[:8], "dimensions": dim},
                    )
                if r.status_code == 200:
                    self._embed_remote_ok = True
                    data = r.json()
                    items = sorted(data["data"], key=lambda x: x["index"])
                    out = [it["embedding"] for it in items]
                    if len(texts) > 8:
                        out.extend(await self.embed(texts[8:], db=db))
                    return out
                self._embed_remote_ok = False
            except Exception:
                self._embed_remote_ok = False
        return local_embed(texts, dim=dim)


gateway = ModelGateway()
