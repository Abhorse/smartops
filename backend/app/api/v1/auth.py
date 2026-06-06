from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_auth_service, get_current_user
from app.core.config import Settings, get_settings
from app.models import User
from app.schemas.auth import AuthTokens, DevAuthRequest, GoogleAuthRequest, RefreshRequest
from app.schemas.common import ApiResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/dev-login", response_model=ApiResponse[AuthTokens])
async def dev_login(
    payload: DevAuthRequest,
    auth_service: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_settings),
) -> ApiResponse[AuthTokens]:
    if not settings.auth_dev_mode:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Dev auth disabled")
    try:
        tokens = await auth_service.dev_login(
            email=payload.email,
            full_name=payload.full_name,
            device_id=payload.device_id,
            device_name=payload.device_name,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return ApiResponse(data=tokens)


@router.post("/google", response_model=ApiResponse[AuthTokens])
async def google_login(
    payload: GoogleAuthRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> ApiResponse[AuthTokens]:
    try:
        tokens = await auth_service.google_login(
            id_token_str=payload.id_token,
            device_id=payload.device_id,
            device_name=payload.device_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ApiResponse(data=tokens)


@router.post("/refresh", response_model=ApiResponse[AuthTokens])
async def refresh_tokens(
    payload: RefreshRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> ApiResponse[AuthTokens]:
    try:
        tokens = await auth_service.refresh(payload.refresh_token, payload.device_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return ApiResponse(data=tokens)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: RefreshRequest,
    user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> None:
    await auth_service.logout(user.id, payload.device_id)
