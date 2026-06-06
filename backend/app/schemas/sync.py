from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class SyncChange(BaseModel):
    id: str
    operation: str
    data: dict[str, Any] = Field(default_factory=dict)
    client_updated_at: Optional[str] = None


class SyncPushRequest(BaseModel):
    device_id: str
    client_schema_version: int = 1
    last_sync_at: Optional[datetime] = None
    changes: dict[str, list[SyncChange]] = Field(default_factory=dict)


class SyncPushResponse(BaseModel):
    accepted: list[str]
    rejected: list[dict[str, Any]]
    conflicts: list[dict[str, Any]]
    server_timestamp: datetime


class SyncPullResponse(BaseModel):
    server_timestamp: datetime
    changes: dict[str, list[dict[str, Any]]]
