"""Host-owned ORM models and shared declarative base.

Tool-specific models live with their plugins and are imported by plugin
discovery before table creation or Alembic schema inspection.
"""

from app.models.audit import ToolCallRecord
from app.models.base import Base, utcnow

__all__ = [
    "Base",
    "utcnow",
    "ToolCallRecord",
]
