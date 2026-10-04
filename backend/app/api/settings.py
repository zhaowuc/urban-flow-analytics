from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user, require_permissions
from backend.app.database.session import get_db
from backend.app.models.entities import SystemSetting, User
from backend.app.services.audit import write_operation_log


router = APIRouter(prefix="/settings", tags=["系统设置"])


class SettingsUpdate(BaseModel):
    values: dict[str, str]


@router.get("")
def list_settings(db: Session = Depends(get_db), _user: User = Depends(get_current_user)) -> dict[str, str]:
    return {item.key: item.value for item in db.scalars(select(SystemSetting)).all()}


@router.put("")
def update_settings(
    payload: SettingsUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(require_permissions("settings:manage")),
) -> dict[str, str]:
    allowed = {"warning.yellow", "warning.orange", "warning.red", "demo.speed"}
    for key, value in payload.values.items():
        if key not in allowed:
            continue
        item = db.scalar(select(SystemSetting).where(SystemSetting.key == key))
        if item:
            item.value = value
    db.commit()
    write_operation_log(db, "update_settings", "system_settings", "更新系统参数", current)
    return {item.key: item.value for item in db.scalars(select(SystemSetting)).all()}

