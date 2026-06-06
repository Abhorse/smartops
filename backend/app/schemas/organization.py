from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class CreateOrganizationRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    business_type: Optional[str] = Field(default=None, max_length=50)
    city: str = Field(min_length=2, max_length=100)
    language: str = Field(default="en", max_length=10)


class OrganizationResponse(BaseModel):
    id: str
    name: str
    business_type: Optional[str] = None
    city: Optional[str] = None
    default_language: str

    model_config = {"from_attributes": True}
