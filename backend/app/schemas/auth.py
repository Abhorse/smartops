from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class AuthDevice(BaseModel):
    device_id: str = Field(min_length=1)
    device_name: Optional[str] = None


class GoogleAuthRequest(AuthDevice):
    id_token: str = Field(min_length=10)


class DevAuthRequest(AuthDevice):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=10)
    device_id: str = Field(min_length=1)


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    avatar_url: Optional[str] = None

    model_config = {"from_attributes": True}


class OrganizationOut(BaseModel):
    id: str
    name: str
    business_type: Optional[str] = None
    city: Optional[str] = None
    role: str

    model_config = {"from_attributes": True}


class AuthTokens(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    user: UserOut
    organizations: list[OrganizationOut]
