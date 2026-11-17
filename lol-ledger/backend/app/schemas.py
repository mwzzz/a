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


class MerchantPurgeIn(BaseModel):
    """清空商家经营数据。必须原样输入商家名，防止误点。"""

    confirm_name: str = Field(min_length=1, max_length=64)
    note: str = Field(default="", max_length=200)


class QueueCreateIn(BaseModel):
    game_id: str = Field(min_length=1, max_length=64)
    note: str = Field(default="", max_length=100)


class QueueStatusIn(BaseModel):
    status: Literal["waiting", "playing", "done", "cancelled"]


class ToolListCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=32)


class ToolItemCreateIn(BaseModel):
    content: str = Field(min_length=1, max_length=64)
    note: str = Field(default="", max_length=100)


class ToolItemUpdateIn(BaseModel):
    content: str | None = Field(default=None, max_length=64)
    note: str | None = Field(default=None, max_length=100)


class ToolMoveIn(BaseModel):
    direction: Literal["up", "down"]


class AiPlayerRef(BaseModel):
    id: int
    game_id: str
    account: str = ""
    deposit_cents: int
    bonus_cents: int = 0
    balance_cents: int
    is_blacklisted: bool = False


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


class DividendSettleIn(BaseModel):
    user_ids: list[int] = Field(min_length=1, max_length=50)
    date_from: str | None = Field(default=None, max_length=20)
    date_to: str | None = Field(default=None, max_length=20)
    note: str = Field(default="", max_length=200)


class PlayerCreateIn(BaseModel):
    game_id: str = Field(min_length=1, max_length=64)
    nickname: str = Field(default="", max_length=64)
    account: str = Field(default="", max_length=64)
    remark: str = Field(default="", max_length=200)
    is_blacklisted: bool = False


class PlayerUpdateIn(BaseModel):
    game_id: str | None = Field(default=None, max_length=64)
    nickname: str | None = Field(default=None, max_length=64)
    account: str | None = Field(default=None, max_length=64)
    remark: str | None = Field(default=None, max_length=200)
    is_blacklisted: bool | None = None


class AmountIn(BaseModel):
    amount_cents: int
    note: str = Field(default="", max_length=200)


class RechargeCampaignIn(BaseModel):
    threshold_cents: int = Field(gt=0)
    bonus_cents: int = Field(gt=0)


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
    dividend_mode: Literal["percent", "fixed"] | None = None
    dividend_fixed_cents: int | None = Field(default=None, ge=0, le=1_000_000)
    shop_name: str | None = Field(default=None, max_length=64)


# ---------------- 查战绩（多用户版） ----------------


class ZjLoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class ZjBatchCreateIn(BaseModel):
    """一次「开始查询」：名单 1~10 人，只扣 1 次额度。"""

    area_id: int = Field(ge=1, le=999)
    all_count: int = Field(default=60, ge=1, le=100)
    # 上限由 settings.zj_batch_max_players 决定（默认 10），这里放宽以免报 422
    players: list[str] = Field(min_length=1, max_length=50)


class ZjQueryIn(BaseModel):
    nickname: str = Field(min_length=3, max_length=80)


class ZjUserCreateIn(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(default="", max_length=64)
    note: str = Field(default="", max_length=200)
    quota_total: int = Field(default=0, ge=0, le=100_000)


class ZjUserUpdateIn(BaseModel):
    display_name: str | None = Field(default=None, max_length=64)
    note: str | None = Field(default=None, max_length=200)
    is_active: bool | None = None


class ZjQuotaGrantIn(BaseModel):
    delta: int = Field(ge=-100_000, le=100_000)
    note: str = Field(default="", max_length=200)
