"""A ready-made ``db`` and abstract ``BaseModel`` for apps that don't have their own."""

from flask_sqlalchemy import SQLAlchemy

from .mixins import BaseModelMixin

db = SQLAlchemy()


class BaseModel(BaseModelMixin, db.Model):  # type: ignore[name-defined]
    """Abstract base bound to this package's ``db``."""

    __abstract__ = True
