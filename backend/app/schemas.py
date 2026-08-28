from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


def ok(data: Any = None, msg: str = "ok") -> dict:
    return {"code": 0, "data": data, "msg": msg}


class SpaceCreate(BaseModel):
    name: str
    security_level: str = "exec"
    confirmer_user_id: Optional[int] = None
    match_rules: list[dict] = Field(default_factory=list)
    report_enabled: bool = True


class SpaceUpdate(BaseModel):
    name: Optional[str] = None
    confirmer_user_id: Optional[int] = None
    match_rules: Optional[list[dict]] = None
    report_enabled: Optional[bool] = None


class FeishuLinkBody(BaseModel):
    url: str
    space_id: int


class DingTalkPullBody(BaseModel):
    conference_id: str
    space_id: int


class EntityPatch(BaseModel):
    payload: Optional[dict] = None
    type: Optional[str] = None
    topic_id: Optional[int] = None


class EntityCreate(BaseModel):
    type: str
    payload: dict
    anchor_segment_ids: list[int]
    topic_id: Optional[int] = None


class ReportGenerate(BaseModel):
    space_id: int
    period_label: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None


class ReportUpdate(BaseModel):
    content_md: str


class SessionCreate(BaseModel):
    space_id: int
    topic_id: Optional[int] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    title: Optional[str] = None


class MessageCreate(BaseModel):
    content: str
