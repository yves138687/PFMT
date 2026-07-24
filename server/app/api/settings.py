from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_client_ip, get_current_user, get_db_session
from app.models.user import UserAccount
from app.schemas.setting import SettingItem, SettingUpdateRequest
from app.services.setting_service import SettingService


router = APIRouter()


@router.get("", response_model=list[SettingItem])
def list_settings(
    _current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> list[SettingItem]:
    """读取系统配置列表，需要登录。"""

    return SettingService(db).list_settings()


@router.put("/{setting_key:path}", response_model=SettingItem)
def update_setting(
    setting_key: str,
    payload: SettingUpdateRequest,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    client_ip: str | None = Depends(get_client_ip),
) -> SettingItem:
    """写入单个系统配置，配置键允许包含点号。"""

    return SettingService(db).update_setting(
        setting_key=setting_key,
        payload=payload,
        updated_by=current_user.user_id,
        client_ip=client_ip,
    )
