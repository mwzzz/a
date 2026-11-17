"""SQLAlchemy 模型。表结构以 migrations.TABLE_STATEMENTS 为准。"""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Merchant(Base):
    __tablename__ = "merchants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    note: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(16), default="active")
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    custodian_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[str] = mapped_column(String(40))
    updated_at: Mapped[str] = mapped_column(String(40))

    @property
    def is_active(self) -> bool:
        return self.status == "active"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"))
    username: Mapped[str] = mapped_column(String(64))
    password_hash: Mapped[str] = mapped_column(String(128))
    display_name: Mapped[str] = mapped_column(String(64), default="")
    role: Mapped[str] = mapped_column(String(16))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superadmin: Mapped[bool] = mapped_column(Boolean, default=False)
    password_changed_at: Mapped[str] = mapped_column(String(40))
    last_login_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[str] = mapped_column(String(40))
    updated_at: Mapped[str] = mapped_column(String(40))

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"))
    game_id: Mapped[str] = mapped_column(String(64))
    nickname: Mapped[str] = mapped_column(String(64), default="")
    account: Mapped[str] = mapped_column(String(64), default="")
    remark: Mapped[str] = mapped_column(String(200), default="")
    is_blacklisted: Mapped[bool] = mapped_column(Boolean, default=False)
    deposit_cents: Mapped[int] = mapped_column(Integer, default=0)
    bonus_cents: Mapped[int] = mapped_column(Integer, default=0)
    games_played: Mapped[int] = mapped_column(Integer, default=0)
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[str] = mapped_column(String(40))
    updated_at: Mapped[str] = mapped_column(String(40))
    deleted_at: Mapped[str | None] = mapped_column(String(40), nullable=True)

    creator: Mapped[User | None] = relationship(User, lazy="joined")


class Batch(Base):
    __tablename__ = "batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"))
    label: Mapped[str] = mapped_column(String(64), default="")
    note: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(16))
    opened_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    opened_at: Mapped[str] = mapped_column(String(40))
    closed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    closed_at: Mapped[str | None] = mapped_column(String(40), nullable=True)

    session_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    player_times: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tea_total_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    add_total_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    refund_total_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deduct_total_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    transfer_out_total_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    transfer_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    net_change_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deposit_total_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dividend_rate_percent: Mapped[int | None] = mapped_column(Integer, default=50)
    # 交班时固化：percent=按茶水比例，fixed=每局固定金额
    dividend_mode: Mapped[str] = mapped_column(String(16), default="percent")
    dividend_fixed_cents: Mapped[int] = mapped_column(Integer, default=0)

    opener: Mapped[User | None] = relationship(User, foreign_keys=[opened_by], lazy="joined")
    closer: Mapped[User | None] = relationship(User, foreign_keys=[closed_by], lazy="joined")


class GameSession(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"))
    name: Mapped[str] = mapped_column(String(64), default="")
    played_at: Mapped[str] = mapped_column(String(40))
    tea_fee_cents: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str] = mapped_column(String(200), default="")
    operator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    player_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String(40))

    operator: Mapped[User | None] = relationship(User, lazy="joined")


class SessionPlayer(Base):
    __tablename__ = "session_players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"))
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"))
    tea_fee_cents: Mapped[int] = mapped_column(Integer, default=0)
    balance_before_cents: Mapped[int] = mapped_column(Integer, default=0)
    balance_after_cents: Mapped[int] = mapped_column(Integer, default=0)
    ledger_id: Mapped[int | None] = mapped_column(ForeignKey("ledger.id"), nullable=True)

    player: Mapped[Player | None] = relationship(Player, lazy="joined")


class LedgerEntry(Base):
    __tablename__ = "ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"))
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"))
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("batches.id"), nullable=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("sessions.id"), nullable=True)
    reason: Mapped[str] = mapped_column(String(24))
    amount_cents: Mapped[int] = mapped_column(Integer)
    balance_before_cents: Mapped[int] = mapped_column(Integer)
    balance_after_cents: Mapped[int] = mapped_column(Integer)
    bonus_amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    deposit_after_cents: Mapped[int] = mapped_column(Integer, default=0)
    bonus_after_cents: Mapped[int] = mapped_column(Integer, default=0)
    counterparty_player_id: Mapped[int | None] = mapped_column(
        ForeignKey("players.id"), nullable=True
    )
    transfer_group_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    operator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    note: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[str] = mapped_column(String(40))


class CashHandover(Base):
    """交班时的现金拆分：茶水营业款上缴管理员，押金余额交给下一保管人。"""

    __tablename__ = "cash_handovers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"))
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"))
    from_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    deposit_to_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    tea_to_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    deposit_cents: Mapped[int] = mapped_column(Integer, default=0)
    tea_cents: Mapped[int] = mapped_column(Integer, default=0)
    deposit_method: Mapped[str] = mapped_column(String(16), default="wechat")
    tea_method: Mapped[str] = mapped_column(String(16), default="wechat")
    note: Mapped[str] = mapped_column(String(200), default="")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[str] = mapped_column(String(40))

    from_user: Mapped[User | None] = relationship(
        User, foreign_keys=[from_user_id], lazy="joined"
    )
    deposit_to: Mapped[User | None] = relationship(
        User, foreign_keys=[deposit_to_user_id], lazy="joined"
    )
    tea_to: Mapped[User | None] = relationship(
        User, foreign_keys=[tea_to_user_id], lazy="joined"
    )


class MerchantSetting(Base):
    __tablename__ = "merchant_settings"

    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), primary_key=True)
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[str] = mapped_column(String(40))
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class RechargeCampaign(Base):
    """充值活动档位：满 threshold_cents 送 bonus_cents，每笔取最高档一次。"""

    __tablename__ = "recharge_campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"))
    threshold_cents: Mapped[int] = mapped_column(Integer)
    bonus_cents: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[str] = mapped_column(String(40))
    updated_at: Mapped[str] = mapped_column(String(40))


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    merchant_id: Mapped[int | None] = mapped_column(
        ForeignKey("merchants.id"), nullable=True
    )
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(32))
    target_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[str] = mapped_column(Text, default="")
    ip: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[str] = mapped_column(String(40))


class DividendSettlement(Base):
    """一次分红结算：某个操作人在一个日期区间内已关班批次的汇总。"""

    __tablename__ = "dividend_settlements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    username_snapshot: Mapped[str] = mapped_column(String(64))
    display_name_snapshot: Mapped[str] = mapped_column(String(64), default="")
    period_start: Mapped[str] = mapped_column(String(40))
    period_end: Mapped[str] = mapped_column(String(40))
    session_count: Mapped[int] = mapped_column(Integer, default=0)
    player_times: Mapped[int] = mapped_column(Integer, default=0)
    tea_cents: Mapped[int] = mapped_column(Integer, default=0)
    dividend_cents: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str] = mapped_column(String(200), default="")
    settled_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[str] = mapped_column(String(40))


class DividendSettlementBatch(Base):
    """结算覆盖的班次。batch_id 唯一，保证一个班次不会被重复结算。"""

    __tablename__ = "dividend_settlement_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    settlement_id: Mapped[int] = mapped_column(ForeignKey("dividend_settlements.id"))
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"))
    session_count: Mapped[int] = mapped_column(Integer, default=0)
    player_times: Mapped[int] = mapped_column(Integer, default=0)
    tea_cents: Mapped[int] = mapped_column(Integer, default=0)
    dividend_cents: Mapped[int] = mapped_column(Integer, default=0)


class ToolList(Base):
    """常用名单的分类，例如「打手」「免押金」。"""

    __tablename__ = "tool_lists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"))
    name: Mapped[str] = mapped_column(String(32))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String(40))
    updated_at: Mapped[str] = mapped_column(String(40))

    items: Mapped[list[ToolItem]] = relationship(
        "ToolItem",
        back_populates="parent",
        cascade="all, delete-orphan",
        order_by="ToolItem.sort_order",
        lazy="selectin",
    )


class ToolItem(Base):
    """名单里的一条记录，content 是名字，note 是可选备注。"""

    __tablename__ = "tool_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    list_id: Mapped[int] = mapped_column(ForeignKey("tool_lists.id"))
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"))
    content: Mapped[str] = mapped_column(String(64))
    note: Mapped[str] = mapped_column(String(100), default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String(40))

    parent: Mapped[ToolList] = relationship("ToolList", back_populates="items")


class QueueEntry(Base):
    """排队登记（小工具）。按自然日展示，跨天不影响历史记录。"""

    __tablename__ = "queue_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"))
    game_id: Mapped[str] = mapped_column(String(64))
    note: Mapped[str] = mapped_column(String(100), default="")
    status: Mapped[str] = mapped_column(String(16), default="waiting")
    operator_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[str] = mapped_column(String(40))
    called_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    finished_at: Mapped[str | None] = mapped_column(String(40), nullable=True)

    operator: Mapped[User | None] = relationship(User, lazy="joined")


class ZjUser(Base):
    """查战绩独立账号：与记账系统的 users 完全解耦，只受配额约束。

    quota_total / quota_used 以「次」为单位，一次 = 点一次「开始查询」，
    与这次查询里包含多少名玩家无关。
    """

    __tablename__ = "zj_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64))
    password_hash: Mapped[str] = mapped_column(String(128))
    display_name: Mapped[str] = mapped_column(String(64), default="")
    note: Mapped[str] = mapped_column(String(200), default="")
    quota_total: Mapped[int] = mapped_column(Integer, default=0)
    quota_used: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    password_changed_at: Mapped[str] = mapped_column(String(40))
    last_login_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[str] = mapped_column(String(40))
    updated_at: Mapped[str] = mapped_column(String(40))

    @property
    def quota_remaining(self) -> int:
        return max(self.quota_total - self.quota_used, 0)

    @property
    def name(self) -> str:
        return self.display_name or self.username


class ZjBatch(Base):
    """一次「开始查询」= 一个批次：开批时扣 1 次额度，之后只能查名单内玩家。

    player_count 是名单人数快照，query_count 记录实际查询人次。
    """

    __tablename__ = "zj_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("zj_users.id"))
    area_id: Mapped[int] = mapped_column(Integer)
    all_count: Mapped[int] = mapped_column(Integer)
    player_count: Mapped[int] = mapped_column(Integer, default=0)
    query_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="open")
    created_at: Mapped[str] = mapped_column(String(40))
    expires_at: Mapped[str] = mapped_column(String(40))
    last_query_at: Mapped[str | None] = mapped_column(String(40), nullable=True)

    user: Mapped[ZjUser | None] = relationship(ZjUser, lazy="joined")

    @property
    def is_open(self) -> bool:
        return self.status == "open"


class ZjBatchPlayer(Base):
    """批次名单：限定该批只能查这些玩家，挡住「扣 1 次后无限查」。"""

    __tablename__ = "zj_batch_players"

    batch_id: Mapped[int] = mapped_column(
        ForeignKey("zj_batches.id"), primary_key=True
    )
    seq: Mapped[int] = mapped_column(Integer, primary_key=True)
    nickname: Mapped[str] = mapped_column(String(80))


class ZjQuery(Base):
    """每次玩家查询一条流水：谁、哪个批次、查了谁、成功与否、查到多少场。"""

    __tablename__ = "zj_queries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("zj_batches.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("zj_users.id"))
    nickname: Mapped[str] = mapped_column(String(80))
    ok: Mapped[bool] = mapped_column(Boolean, default=False)
    err_code: Mapped[str] = mapped_column(String(32), default="")
    games: Mapped[int] = mapped_column(Integer, default=0)
    ip: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[str] = mapped_column(String(40))


class ZjGrant(Base):
    """配额调整流水：管理员加/减次数，operator_id 指向记账系统的开发者账号。"""

    __tablename__ = "zj_grants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("zj_users.id"))
    delta: Mapped[int] = mapped_column(Integer)
    quota_after: Mapped[int] = mapped_column(Integer)
    operator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    note: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[str] = mapped_column(String(40))

    operator: Mapped[User | None] = relationship(User, lazy="joined")
