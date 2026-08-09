from datetime import datetime, timezone

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    """Naive UTC now, matching Postgres ``now()`` column storage.

    Avoids the deprecated ``datetime.utcnow`` while keeping stored values
    consistent with the DB ``server_default`` (which is naive UTC).
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
