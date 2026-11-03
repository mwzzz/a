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


class MerchantCreateIn(BaseModel):
    """开发者开通商家。管理员可以同时建，也可以稍后再建。"""

    name: str = Field(min_length=1, max_length=64)
    note: str = Field(default="", max_length=200)
    admin_username: str | None = Field(default=None, max_length=64)
    admin_password: str | None = Field(default=None, max_length=128)
    admin_display_name: str = Field(default="", max_length=64)


class MerchantUpdateIn(BaseModel):
    name: str | None = Field(default=None, max_length=64)
    note: str | None = Field(default=None, max_length=200)
    status: Literal["active", "disabled"] | None = None


class AiPlayerRef(BaseModel):
    id: int
    game_id: str
    account: str = ""
    deposit_cents: int


class AiCandidateOut(BaseModel):
    player: AiPlayerRef
    score: float


class AiPlayerItemOut(BaseModel):
    raw_name: str
    status: Literal["matched", "ambiguous", "unmatched"]
    confidence: float | None = None
    team: int | None = None
    matched_player: AiPlayerRef | None = None
    candidates: list[AiCandidateOut] = Field(default_factory=list)


class AiRecognizeOut(BaseModel):
    items: list[AiPlayerItemOut]
    count: int
    warnings: list[str] = Field(default_factory=list)
    elapsed_ms: int


class AiStatusOut(BaseModel):
    enabled: bool
    model: str


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
    """交班：茶水营业款上缴管理员，押金余额交给下一保管人。"""

    tea_to_user_id: int
    deposit_to_user_id: int
    tea_method: str = Field(default="wechat", max_length=16)
    deposit_method: str = Field(default="wechat", max_length=16)
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
    dividend_rate_percent: int | None = Field(default=None, ge=0, le=100)
    shop_name: str | None = Field(default=None, max_length=64)
