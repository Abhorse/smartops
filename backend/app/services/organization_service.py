from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ExpenseCategory, Organization, OrganizationMember, ProductCategory, RevenueCategory, Role, User, UserPreference
from app.services.auth_service import slugify


DEFAULT_EXPENSE_CATEGORIES = [
    ("Utilities", "#0D6E6E"),
    ("Rent", "#5C6BC0"),
    ("Raw Materials", "#8D6E63"),
    ("Transport", "#26A69A"),
    ("Maintenance", "#78909C"),
    ("Other", "#9E9E9E"),
]


DEFAULT_REVENUE_CATEGORIES = [
    "Product Sales",
    "Service Income",
    "Other",
]

DEFAULT_PRODUCT_CATEGORIES = [
    "General",
    "Grocery",
    "Raw Materials",
    "Packaged Goods",
]


class OrganizationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_organization(
        self,
        user: User,
        name: str,
        city: str,
        business_type: str | None,
        language: str,
    ) -> Organization:
        owner_role = await self.session.scalar(select(Role).where(Role.name == "owner"))
        if owner_role is None:
            raise RuntimeError("Owner role is not seeded")

        base_slug = slugify(name)
        slug = base_slug
        suffix = 1
        while await self.session.scalar(select(Organization).where(Organization.slug == slug)):
            slug = f"{base_slug}-{suffix}"
            suffix += 1

        org = Organization(
            name=name,
            slug=slug,
            business_type=business_type,
            city=city,
            default_language=language,
        )
        self.session.add(org)
        await self.session.flush()

        self.session.add(
            OrganizationMember(
                organization_id=org.id,
                user_id=user.id,
                role_id=owner_role.id,
                joined_at=org.created_at,
            )
        )

        prefs = await self.session.scalar(select(UserPreference).where(UserPreference.user_id == user.id))
        if prefs:
            prefs.language = language

        for category_name, color in DEFAULT_EXPENSE_CATEGORIES:
            self.session.add(
                ExpenseCategory(
                    organization_id=org.id,
                    name=category_name,
                    color=color,
                    is_default=True,
                )
            )

        for category_name in DEFAULT_REVENUE_CATEGORIES:
            self.session.add(
                RevenueCategory(
                    organization_id=org.id,
                    name=category_name,
                    is_default=True,
                )
            )

        for category_name in DEFAULT_PRODUCT_CATEGORIES:
            self.session.add(
                ProductCategory(
                    organization_id=org.id,
                    name=category_name,
                    is_default=True,
                )
            )

        await self.session.commit()
        await self.session.refresh(org)
        return org
