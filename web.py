import os
import secrets
from datetime import time as dt_time
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field, model_validator

import storage

INDEX_HTML = Path(__file__).parent / "static" / "index.html"
security = HTTPBasic()


def require_admin(credentials: HTTPBasicCredentials = Depends(security)) -> None:
    password = os.getenv("ADMIN_PASSWORD") or ""
    username = os.getenv("ADMIN_USER") or "admin"
    user_ok = secrets.compare_digest(credentials.username.encode(), username.encode())
    pass_ok = secrets.compare_digest(credentials.password.encode(), password.encode())
    if not (password and user_ok and pass_ok):
        raise HTTPException(status_code=401, detail="Unauthorized", headers={"WWW-Authenticate": "Basic"})


class SettingsIn(BaseModel):
    is_active: bool
    mode: Literal["plain", "html"]
    default_message: str = Field(min_length=1, max_length=2000)


class RuleIn(BaseModel):
    user_id: int = Field(gt=0)
    label: str = Field(default="", max_length=100)
    message: str = Field(min_length=1, max_length=2000)
    start_time: str | None = None  # "HH:MM"; ikkalasi ham bo'lsa, vaqt oralig'i ishlaydi
    end_time: str | None = None
    enabled: bool = True

    @model_validator(mode="after")
    def check_window(self):
        if (self.start_time is None) != (self.end_time is None):
            raise ValueError("start_time va end_time birgalikda berilishi kerak")
        for value in (self.start_time, self.end_time):
            if value is not None:
                dt_time.fromisoformat(value)  # noto'g'ri format bo'lsa ValueError
        return self


app = FastAPI(
    title="Auto-reply admin",
    dependencies=[Depends(require_admin)],
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


def _state() -> dict:
    settings = storage.get_settings()
    return {
        "settings": {
            "is_active": settings.get("is_active") == "1",
            "mode": settings.get("mode", "html"),
            "default_message": settings.get("default_message", ""),
        },
        "rules": [{**rule, "enabled": bool(rule["enabled"])} for rule in storage.list_rules()],
    }


@app.get("/")
def index() -> FileResponse:
    return FileResponse(INDEX_HTML)


@app.get("/api/state")
def get_state() -> dict:
    return _state()


@app.put("/api/settings")
def update_settings(body: SettingsIn) -> dict:
    storage.set_setting("is_active", "1" if body.is_active else "0")
    storage.set_setting("mode", body.mode)
    storage.set_setting("default_message", body.default_message)
    return _state()


@app.post("/api/rules")
def save_rule(body: RuleIn) -> dict:
    storage.upsert_rule(
        user_id=body.user_id,
        label=body.label.strip(),
        message=body.message,
        start_time=body.start_time,
        end_time=body.end_time,
        enabled=body.enabled,
    )
    return _state()


@app.delete("/api/rules/{user_id}")
def delete_rule(user_id: int) -> dict:
    if not storage.delete_rule(user_id):
        raise HTTPException(status_code=404, detail="Qoida topilmadi")
    return _state()
