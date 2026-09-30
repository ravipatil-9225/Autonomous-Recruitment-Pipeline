"""
Database Base + SQLAlchemy declarative setup.
All ORM models import from here.
"""

from sqlalchemy.orm import DeclarativeBase, declared_attr


class Base(DeclarativeBase):
    """Shared declarative base for all ARP ORM models."""

    @declared_attr.directive
    def __tablename__(cls) -> str:
        # Default table name = lowercase class name; override per model if needed
        return cls.__name__.lower()
