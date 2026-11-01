"""接口请求体。业务校验（金额、权限）放在 service 层，这里只做类型约束。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class ChangePasswordIn(BaseModel):
    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=1, max_length=128)


class UserCreateIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)
    display_name: str = Field(default="", max_length=64)
    role: Literal["admin", "staff"] = "staff"


class UserUpdateIn(BaseModel):
    display_name: str | None = Field(default=None, max_length=64)
    role: Literal["admin", "staff"] | None = None
    is_active: bool | None = None


class PasswordResetIn(BaseModel):
    new_password: str = Field(min_length=1, max_length=128)


class PlayerCreateIn(BaseModel):
    game_id: str = Field(min_length=1, max_length=64)
    nickname: str = Field(default="", max_length=64)
    account: str = Field(default="", max_length=64)
    remark: str = Field(default="", max_length=200)


class PlayerUpdateIn(BaseModel):
    game_id: str | None = Field(default=None, max_length=64)
    nickname: str | None = Field(default=None, max_length=64)
    account: str | None = Field(default=None, max_length=64)
    remark: str | None = Field(default=None, max_length=200)


class AmountIn(BaseModel):
    amount_cents: int
    note: str = Field(default="", max_length=200)


class TransferIn(BaseModel):
    from_player_id: int
    to_player_id: int
    amount_cents: int
    note: str = Field(default="", max_length=200)


class BatchCreateIn(BaseModel):
    label: str = Field(default="", max_length=64)
    note: str = Field(default="", max_length=200)


class BatchCloseIn(BaseModel):
    note: str = Field(default="", max_length=200)


class SessionPreviewIn(BaseModel):
    player_ids: list[int] = []
    tea_fee_cents: int = 0


class SessionCreateIn(BaseModel):
    batch_id: int | None = None
    name: str = Field(default="", max_length=64)
    played_at: str | None = None
    note: str = Field(default="", max_length=200)
    tea_fee_cents: int = 0
    player_ids: list[int] = []


class SettingsUpdateIn(BaseModel):
    last_tea_cents: int | None = None
    deposit_low_cents: int | None = None
    deposit_high_cents: int | None = None
    shop_name: str | None = Field(default=None, max_length=64)
