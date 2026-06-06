from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import get_current_user, get_db
from app.models import OrganizationMember, User
from app.schemas.common import ApiResponse
from app.schemas.organization import CreateOrganizationRequest, OrganizationResponse
from app.services.organization_service import OrganizationService
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post("", response_model=ApiResponse[OrganizationResponse], status_code=status.HTTP_201_CREATED)
async def create_organization(
    payload: CreateOrganizationRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[OrganizationResponse]:
    existing = await session.scalar(
        select(OrganizationMember).where(
            OrganizationMember.user_id == user.id,
            OrganizationMember.is_active.is_(True),
        )
    )
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already belongs to an organization")

    service = OrganizationService(session)
    org = await service.create_organization(
        user=user,
        name=payload.name,
        city=payload.city,
        business_type=payload.business_type,
        language=payload.language,
    )
    return ApiResponse(
        data=OrganizationResponse(
            id=org.id,
            name=org.name,
            business_type=org.business_type,
            city=org.city,
            default_language=org.default_language,
        )
    )
