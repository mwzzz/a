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
    deposit_cents: Mapped[int] = mapped_column(Integer, default=0)
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

    opener: Mapped[User | None] = relationship(User, foreign_keys=[opened_by], lazy="joined")
    closer: Mapped[User | None] = relationship(User, foreign_keys=[closed_by], lazy="joined")


class GameSession(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"))
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"))
    name: Mapped[str] = mapped_column(String(64), default="")
    played_at: Mapped[str] = mapped_column(String(40))
    tea_fee_cents: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str] = mapped_column(String(200), default="")
    operator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    player_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String(40))

    operator: Mapped[User | None] = relationship(User, lazy="joined")
    batch: Mapped[Batch | None] = relationship(Batch, lazy="joined")


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
    counterparty_player_id: Mapped[int | None] = mapped_column(
        ForeignKey("players.id"), nullable=True
    )
    transfer_group_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    operator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    note: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[str] = mapped_column(String(40))


class MerchantSetting(Base):
    __tablename__ = "merchant_settings"

    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), primary_key=True)
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[str] = mapped_column(String(40))
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


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
