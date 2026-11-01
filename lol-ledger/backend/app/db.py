"""SQLite 连接管理。

写连接用 `BEGIN IMMEDIATE`（开始就拿写锁，避免读后写升级死锁），
读连接走默认事务，WAL 下读写互不阻塞。
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

logger = logging.getLogger(__name__)

_write_engine = None
_read_engine = None
_db_path: Path | None = None
WriteSession: sessionmaker | None = None
ReadSession: sessionmaker | None = None


def _make_engine(path: Path, *, write: bool):
    engine = create_engine(
        f"sqlite+pysqlite:///{path}",
        connect_args={
            "timeout": 5,
            "check_same_thread": False,
            "isolation_level": None,
        },
        pool_pre_ping=True,
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_connection, _record) -> None:  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.execute("PRAGMA temp_store=MEMORY")
        finally:
            cursor.close()

    if write:

        @event.listens_for(engine, "begin")
        def _begin_immediate(conn) -> None:  # noqa: ANN001
            conn.exec_driver_sql("BEGIN IMMEDIATE")

    return engine


def configure_db(path: Path | str | None = None) -> None:
    """建立（或重建）读写引擎。测试里会反复调用。"""
    global _write_engine, _read_engine, _db_path, WriteSession, ReadSession
    dispose()

    target = Path(path or settings.db_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    _db_path = target

    _write_engine = _make_engine(target, write=True)
    _read_engine = _make_engine(target, write=False)
    WriteSession = sessionmaker(bind=_write_engine, expire_on_commit=False, future=True)
    ReadSession = sessionmaker(bind=_read_engine, expire_on_commit=False, future=True)


def dispose() -> None:
    global _write_engine, _read_engine
    if _write_engine is not None:
        _write_engine.dispose()
        _write_engine = None
    if _read_engine is not None:
        _read_engine.dispose()
        _read_engine = None


def current_path() -> Path:
    """当前库文件路径。迁移脚本要用它做备份和直连。"""
    if _db_path is None:
        raise RuntimeError("数据库尚未初始化")
    return _db_path


def ensure_schema() -> None:
    from app import migrations

    migrations.ensure_schema()


@contextmanager
def write_session() -> Iterator[Session]:
    """写事务：begin 事件会发 BEGIN IMMEDIATE，退出时提交，异常回滚。"""
    assert WriteSession is not None, "数据库尚未初始化"
    session: Session = WriteSession()
    try:
        with session.begin():
            yield session
    finally:
        session.close()


@contextmanager
def read_session() -> Iterator[Session]:
    assert ReadSession is not None, "数据库尚未初始化"
    session: Session = ReadSession()
    try:
        yield session
    finally:
        session.close()


def sqlite_version() -> str:
    import sqlite3

    return sqlite3.sqlite_version


configure_db()
logger.info("数据库已配置：%s (sqlite %s)", settings.db_path, sqlite_version())
