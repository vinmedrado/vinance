
from __future__ import annotations

from contextlib import contextmanager

from backend.app.core.sync_database import get_sync_session, sync_session


@contextmanager
def db_session():
    with sync_session() as db:
        yield db


def get_db():
    yield from get_sync_session()
