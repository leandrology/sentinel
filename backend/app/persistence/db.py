"""Sync SQLite engine + session factory.

Async workers call repository functions via ``asyncio.to_thread`` so the
event loop never blocks on SQLite I/O. ``check_same_thread=False`` is
required for that handoff.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.persistence.models import Base

_engine = None
_Session: sessionmaker | None = None


def init_db(url: str) -> sessionmaker:
    global _engine, _Session
    _engine = create_engine(url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(_engine)
    _Session = sessionmaker(bind=_engine, expire_on_commit=False)
    return _Session


def get_session_factory() -> sessionmaker:
    if _Session is None:
        raise RuntimeError("database not initialized; call init_db first")
    return _Session
