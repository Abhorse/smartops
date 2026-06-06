from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    hash_token,
)
from app.models import Organization, OrganizationMember, RefreshToken, Role, User, UserPreference
from app.schemas.auth import AuthTokens, OrganizationOut, UserOut


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:90] or "business"


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings):
        self.session = session
        self.settings = settings

    async def _load_user(self, user_id: str) -> User | None:
        result = await self.session.execute(
            select(User)
            .where(User.id == user_id, User.is_active.is_(True))
            .options(
                selectinload(User.memberships)
                .selectinload(OrganizationMember.organization),
                selectinload(User.memberships).selectinload(OrganizationMember.role),
            )
        )
        return result.scalar_one_or_none()

    async def _organizations_for_user(self, user: User) -> list[OrganizationOut]:
        result = await self.session.execute(
            select(OrganizationMember)
            .where(
                OrganizationMember.user_id == user.id,
                OrganizationMember.is_active.is_(True),
            )
            .options(
                selectinload(OrganizationMember.organization),
                selectinload(OrganizationMember.role),
            )
        )
        orgs: list[OrganizationOut] = []
        for membership in result.scalars():
            if membership.organization.deleted_at is not None:
                continue
            orgs.append(
                OrganizationOut(
                    id=membership.organization.id,
                    name=membership.organization.name,
                    business_type=membership.organization.business_type,
                    city=membership.organization.city,
                    role=membership.role.name,
                )
            )
        return orgs

    async def _issue_tokens(self, user: User, device_id: str, device_name: str | None) -> AuthTokens:
        user.last_login_at = datetime.now(timezone.utc)
        await self._revoke_device_tokens(user.id, device_id)

        refresh_plain = create_refresh_token()
        refresh = RefreshToken(
            user_id=user.id,
            token_hash=hash_token(refresh_plain),
            device_id=device_id,
            device_name=device_name,
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=self.settings.refresh_token_expire_days),
        )
        self.session.add(refresh)
        orgs = await self._organizations_for_user(user)
        await self.session.commit()
        await self.session.refresh(user)

        access = create_access_token(user.id, self.settings)
        return AuthTokens(
            access_token=access,
            refresh_token=refresh_plain,
            expires_in=self.settings.access_token_expire_minutes * 60,
            user=UserOut.model_validate(user),
            organizations=orgs,
        )

    async def _revoke_device_tokens(self, user_id: str, device_id: str) -> None:
        result = await self.session.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.device_id == device_id,
                RefreshToken.revoked_at.is_(None),
            )
        )
        for token in result.scalars():
            token.revoked_at = datetime.now(timezone.utc)
        await self.session.flush()

    async def dev_login(self, email: str, full_name: str, device_id: str, device_name: str | None) -> AuthTokens:
        if not self.settings.auth_dev_mode:
            raise PermissionError("Dev auth disabled")

        result = await self.session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(
                email=email,
                full_name=full_name,
                google_sub=f"dev-{email}",
                auth_provider="google",
            )
            self.session.add(user)
            await self.session.flush()
            self.session.add(UserPreference(user_id=user.id, language="en"))
            await self.session.flush()

        return await self._issue_tokens(user, device_id, device_name)

    async def google_login(
        self, id_token_str: str, device_id: str, device_name: str | None
    ) -> AuthTokens:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token

        if not self.settings.google_client_id:
            raise ValueError("Google Sign-In is not configured on the server")

        idinfo = id_token.verify_oauth2_token(
            id_token_str,
            google_requests.Request(),
            self.settings.google_client_id,
        )
        google_sub = idinfo["sub"]
        email = idinfo["email"]
        full_name = idinfo.get("name") or email.split("@")[0]
        avatar_url = idinfo.get("picture")

        result = await self.session.execute(select(User).where(User.google_sub == google_sub))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(
                google_sub=google_sub,
                email=email,
                full_name=full_name,
                avatar_url=avatar_url,
                auth_provider="google",
            )
            self.session.add(user)
            await self.session.flush()
            self.session.add(UserPreference(user_id=user.id, language="en"))
        else:
            user.email = email
            user.full_name = full_name
            user.avatar_url = avatar_url

        await self.session.flush()
        return await self._issue_tokens(user, device_id, device_name)

    async def refresh(self, refresh_token: str, device_id: str) -> AuthTokens:
        token_hash = hash_token(refresh_token)
        result = await self.session.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.device_id == device_id,
                RefreshToken.revoked_at.is_(None),
            )
        )
        stored = result.scalar_one_or_none()
        now = datetime.now(timezone.utc)
        expires_at = stored.expires_at if stored is None else stored.expires_at
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if stored is None or expires_at < now:
            raise ValueError("Invalid refresh token")

        user = await self._load_user(stored.user_id)
        if user is None:
            raise ValueError("User not found")

        return await self._issue_tokens(user, device_id, stored.device_name)

    async def logout(self, user_id: str, device_id: str) -> None:
        await self._revoke_device_tokens(user_id, device_id)
        await self.session.commit()

    async def get_current_user(self, access_token: str) -> User:
        user_id = decode_access_token(access_token, self.settings)
        user = await self._load_user(user_id)
        if user is None:
            raise ValueError("User not found")
        return user
