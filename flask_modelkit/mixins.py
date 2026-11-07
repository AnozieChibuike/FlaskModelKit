"""
Composable model mixins for Flask-SQLAlchemy.

Mixins go *before* ``db.Model`` in the class bases::

    class Post(UUIDMixin, TimestampMixin, SoftDeleteMixin, CRUDMixin, db.Model):
        ...
"""

from __future__ import annotations

import enum
import json
import uuid
import weakref
from collections.abc import Mapping
from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Any, ClassVar, Iterable, NoReturn, TypedDict, TypeVar

import sqlalchemy as sa
from flask import abort
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import (
    Mapped,
    ORMExecuteState,
    Session,
    mapped_column,
    with_loader_criteria,
)
from werkzeug.exceptions import BadRequest, Conflict

__all__ = [
    "UUIDMixin",
    "IntIdMixin",
    "TimestampMixin",
    "SoftDeleteMixin",
    "CRUDMixin",
    "SerializerMixin",
    "BaseModelMixin",
    "PaginationReturn",
    "InvalidBodyError",
    "MissingFieldsError",
    "DuplicateValueError",
    "hidden_column",
    "utcnow",
]

T = TypeVar("T", bound="CRUDMixin")


def utcnow() -> datetime:
    """Current UTC time as a naive ``datetime``.

    Naive so values round-trip identically on every backend (SQLite drops
    tzinfo). All timestamps written by this package are UTC.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _new_uuid() -> str:
    return str(uuid.uuid4())


class _SessionMixin:
    """Finds the Flask-SQLAlchemy extension that owns the model."""

    @classmethod
    def _db(cls) -> SQLAlchemy:
        fsa = getattr(cls, "__fsa__", None)
        if fsa is None:
            raise TypeError(
                f"{cls.__name__} must also inherit from a Flask-SQLAlchemy "
                f"db.Model, e.g. class {cls.__name__}(CRUDMixin, db.Model)"
            )
        return fsa

    @classmethod
    def _session(cls) -> Session:
        return cls._db().session  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Primary keys
# ---------------------------------------------------------------------------


class UUIDMixin:
    """UUID4 string primary key, assigned when the object is constructed so
    it can be used before the first flush."""

    id: Mapped[str] = mapped_column(sa.String(126), primary_key=True, default=_new_uuid)

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("id", _new_uuid())
        super().__init__(**kwargs)


class IntIdMixin:
    """Auto-incrementing integer primary key, assigned by the database."""

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)


# ---------------------------------------------------------------------------
# Timestamps
# ---------------------------------------------------------------------------


class TimestampMixin:
    """``created_at`` / ``updated_at`` in UTC.

    ``updated_at`` is refreshed whenever the row is UPDATEd, whether through
    ``save()``/``update()`` or a plain ``db.session.commit()``.
    """

    created_at: Mapped[datetime] = mapped_column(sa.DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    def __init__(self, **kwargs: Any) -> None:
        now = utcnow()
        kwargs.setdefault("created_at", now)
        kwargs.setdefault("updated_at", now)
        super().__init__(**kwargs)


# ---------------------------------------------------------------------------
# Soft delete
# ---------------------------------------------------------------------------


class SoftDeleteMixin(_SessionMixin):
    """Mark rows deleted instead of removing them.

    Soft-deleted rows are hidden from **every** ORM query on the model:
    ``Model.all()``, ``Model.query``, ``db.select(Model)``, ``session.get()``
    and relationship loads. To include them, add
    ``.execution_options(include_deleted=True)`` to a statement or use
    ``Model.select(include_deleted=True)``.
    """

    deleted_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime, nullable=True, default=None, index=True
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def soft_delete(self, commit: bool = True) -> None:
        """Set ``deleted_at`` to now. The row stays in the table."""
        self.deleted_at = utcnow()
        self._persist(commit)

    def restore(self, commit: bool = True) -> None:
        """Clear ``deleted_at`` so the row is visible again."""
        self.deleted_at = None
        self._persist(commit)

    def _persist(self, commit: bool) -> None:
        session = self._session()
        session.add(self)
        if commit:
            session.commit()


@event.listens_for(Session, "do_orm_execute")
def _hide_soft_deleted(state: ORMExecuteState) -> None:
    if (
        state.is_select
        and not state.is_column_load
        and not state.is_relationship_load
        and not state.execution_options.get("include_deleted", False)
    ):
        state.statement = state.statement.options(
            with_loader_criteria(
                SoftDeleteMixin,
                lambda cls: cls.deleted_at.is_(None),
                include_aliases=True,
            )
        )


# ---------------------------------------------------------------------------
# CRUD and queries
# ---------------------------------------------------------------------------


class _JSONHTTPError:
    """Renders a Werkzeug HTTP error as a JSON body:
    ``{"error": ..., "message": ..., "fields": [...]}``."""

    error: ClassVar[str] = "error"
    fields: list[str]
    description: str | None

    def get_body(self, environ: Any = None, scope: Any = None) -> str:
        return json.dumps(
            {"error": self.error, "message": self.description, "fields": self.fields}
        )

    def get_headers(self, environ: Any = None, scope: Any = None) -> list[tuple[str, str]]:
        return [("Content-Type", "application/json")]


class InvalidBodyError(_JSONHTTPError, BadRequest):
    """400: the input was not a JSON object (dict)."""

    error = "invalid_body"

    def __init__(self) -> None:
        self.fields = []
        super().__init__(description="Request body must be a JSON object.")


class MissingFieldsError(_JSONHTTPError, BadRequest):
    """400: required fields were missing or blank. ``.fields`` lists them."""

    error = "missing_fields"

    def __init__(self, fields: Iterable[str]) -> None:
        self.fields = list(fields)
        super().__init__(description="Missing required field(s): " + ", ".join(self.fields))


class DuplicateValueError(_JSONHTTPError, Conflict):
    """409: a unique field's value is already taken. ``.fields`` lists them."""

    error = "duplicate"

    def __init__(self, model: str, fields: Iterable[str]) -> None:
        self.fields = list(fields)
        super().__init__(
            description=f"A {model} with this {', '.join(self.fields)} already exists."
        )


def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


_required_cache: weakref.WeakKeyDictionary[type, tuple[str, ...]] = weakref.WeakKeyDictionary()


def _required_columns(cls: type) -> tuple[str, ...]:
    """Attribute keys of NOT NULL columns with no default, in declaration order."""
    keys = _required_cache.get(cls)
    if keys is None:
        found = []
        for attr in sa.inspect(cls).column_attrs:
            col = attr.columns[0]
            if not isinstance(col, sa.Column) or col.nullable:
                continue
            if col.default is not None or col.server_default is not None:
                continue
            if col.table is not None and col is col.table.autoincrement_column:
                continue
            found.append(attr.key)
        keys = _required_cache[cls] = tuple(found)
    return keys


class PaginationReturn(TypedDict):
    items: list[Any]
    total: int
    pages: int
    page: int
    per_page: int


class CRUDMixin(_SessionMixin):
    """``save``/``update``/``delete`` plus class-level query helpers."""

    #: Attributes ``update()`` will never set. Extend per model:
    #: ``__protected_fields__ = CRUDMixin.__protected_fields__ | {"is_admin"}``
    __protected_fields__: ClassVar[frozenset[str]] = frozenset(
        {"id", "created_at", "updated_at", "deleted_at"}
    )

    # -- instance methods ---------------------------------------------------

    def save(self, commit: bool = True) -> None:
        """Add to the session and commit. ``commit=False`` lets you group
        several changes into one transaction and commit yourself."""
        session = self._session()
        session.add(self)
        if commit:
            session.commit()

    def update(self, updates: dict[str, Any], commit: bool = True) -> None:
        """Set mapped attributes from ``updates`` and save.

        Unknown keys and ``__protected_fields__`` are ignored, so request
        JSON can be passed straight in.
        """
        allowed = self._writable_fields()
        for key, value in updates.items():
            if key in allowed:
                setattr(self, key, value)
        self.save(commit=commit)

    def delete(self, commit: bool = True) -> None:
        """Remove the row from the database (a hard delete, even on
        ``SoftDeleteMixin`` models; use ``soft_delete()`` for those)."""
        session = self._session()
        session.delete(self)
        if commit:
            session.commit()

    def close(self) -> None:
        """Remove the current scoped session."""
        self._session().remove()  # type: ignore[attr-defined]

    # -- class methods ------------------------------------------------------

    @classmethod
    def select(cls, include_deleted: bool = False) -> sa.Select[Any]:
        """A ``select(Model)`` statement to build custom queries on."""
        stmt = sa.select(cls)
        if include_deleted:
            stmt = stmt.execution_options(include_deleted=True)
        return stmt

    @classmethod
    def create(cls: type[T], commit: bool = True, **kwargs: Any) -> T:
        """Construct, save and return a new object."""
        obj = cls(**kwargs)
        obj.save(commit=commit)
        return obj

    @classmethod
    def _writable_fields(cls) -> set[str]:
        """Mapped columns/relationships that untrusted input may set."""
        return set(sa.inspect(cls).attrs.keys()) - cls.__protected_fields__

    @classmethod
    def create_or_abort(
        cls: type[T],
        data: Mapping[str, Any] | None,
        *,
        fields: Iterable[str] | None = None,
        required: Iterable[str] = (),
        commit: bool = True,
        **values: Any,
    ) -> T:
        """Create from untrusted input (e.g. ``request.json``) or raise a
        JSON HTTP error.

        - Keys that aren't mapped attributes, or are in ``__protected_fields__``,
          are dropped. ``fields`` narrows what's accepted to an allowlist.
        - ``values`` are trusted keyword arguments (e.g. ``author=current_user``,
          a password hash). They override ``data`` and skip protection.
        - NOT NULL columns without a default are required. Passing a
          relationship (``author=...``) satisfies its foreign-key column.
          ``required`` adds names that must be present in ``data`` even if
          they aren't columns (e.g. ``"password"``). ``None`` and blank
          strings count as missing.

        Raises:
            InvalidBodyError: 400, ``data`` is not a mapping.
            MissingFieldsError: 400, listing every missing field.
            DuplicateValueError: 409, a unique value is taken. The session is
                rolled back (including other uncommitted changes).

        Other ``IntegrityError``s are re-raised after rolling back, so
        genuine bugs aren't hidden behind a 409.
        """
        if data is None:
            data = {}
        if not isinstance(data, Mapping):
            raise InvalidBodyError()

        accepted = cls._writable_fields()  # type: ignore[attr-defined]
        if fields is not None:
            accepted &= set(fields)
        accepted -= values.keys()
        clean = {k: v for k, v in data.items() if k in accepted}
        kwargs = {**clean, **values}

        mapper = sa.inspect(cls)
        satisfied = {k for k, v in kwargs.items() if not _blank(v)}
        for rel in mapper.relationships:
            if rel.key in satisfied:
                for col in rel.local_columns:
                    satisfied.add(mapper.get_property_by_column(col).key)

        missing = [k for k in _required_columns(cls) if k in accepted and k not in satisfied]
        missing += [
            k for k in required
            if k not in values and _blank(data.get(k)) and k not in missing
        ]
        if missing:
            raise MissingFieldsError(missing)

        obj = cls(**kwargs)
        session = cls._session()
        session.add(obj)
        try:
            session.flush()
            if commit:
                session.commit()
        except IntegrityError:
            session.rollback()
            taken = cls._taken_unique_fields(kwargs)  # type: ignore[attr-defined]
            if taken:
                raise DuplicateValueError(cls.__name__, taken) from None
            raise
        return obj

    @classmethod
    def _taken_unique_fields(cls, values: Mapping[str, Any]) -> list[str]:
        """Which unique fields in ``values`` already exist in the table
        (soft-deleted rows included, since constraints still see them)."""
        mapper = sa.inspect(cls)
        groups: list[list[Any]] = []
        for table in mapper.tables:
            groups.append(list(table.primary_key.columns))
            for cons in table.constraints:
                if isinstance(cons, sa.UniqueConstraint):
                    groups.append(list(cons.columns))
            for index in table.indexes:
                if index.unique:
                    groups.append(list(index.columns))

        taken: list[str] = []
        session = cls._session()
        for cols in groups:
            try:
                keys = [mapper.get_property_by_column(c).key for c in cols]
            except Exception:
                continue
            if not keys or any(k not in values or values[k] is None for k in keys):
                continue
            stmt = (
                sa.select(cls)
                .filter_by(**{k: values[k] for k in keys})
                .limit(1)
                .execution_options(include_deleted=True)
            )
            if session.scalars(stmt).first() is not None:
                taken += [k for k in keys if k not in taken]
        return taken

    @classmethod
    def all(cls: type[T]) -> list[T]:
        return list(cls._session().scalars(sa.select(cls)))

    @classmethod
    def get(cls: type[T], id: Any, include_deleted: bool = False) -> T | None:
        """Object with primary key ``id``, or None."""
        if id is None or id == "":
            return None
        obj = cls._session().get(
            cls, id, execution_options={"include_deleted": include_deleted}
        )
        # The identity map can return an object soft-deleted in this session.
        if obj is not None and not include_deleted and getattr(obj, "deleted_at", None):
            return None
        return obj

    @classmethod
    def get_or_404(cls: type[T], id: Any) -> T | NoReturn:
        """Object with primary key ``id``, or abort with HTTP 404."""
        return cls.get(id) or abort(404, description=f"{cls.__name__} not found")

    @classmethod
    def filter_one(cls: type[T], **filters: Any) -> T | None:
        """First object matching ``column=value`` filters, or None."""
        return cls._session().scalars(sa.select(cls).filter_by(**filters).limit(1)).first()

    @classmethod
    def filter_all(cls: type[T], **filters: Any) -> list[T]:
        """All objects matching ``column=value`` filters."""
        return list(cls._session().scalars(sa.select(cls).filter_by(**filters)))

    @classmethod
    def filter_and_count_all(cls, **filters: Any) -> int:
        """Number of rows matching ``column=value`` filters (SQL ``COUNT``)."""
        session = cls._session()
        stmt = sa.select(sa.func.count()).select_from(cls).filter_by(**filters)
        return session.scalar(stmt) or 0

    @classmethod
    def count_all(cls) -> int:
        """Total number of rows (SQL ``COUNT``; rows are not loaded)."""
        return cls.filter_and_count_all()

    @classmethod
    def exists(cls, **filters: Any) -> bool:
        """Whether any row matches ``column=value`` filters."""
        session = cls._session()
        return bool(session.scalar(sa.select(sa.select(cls).filter_by(**filters).exists())))

    @classmethod
    def paginate(cls, page: int = 1, per_page: int = 10) -> PaginationReturn:
        """One page of objects, ordered by ``created_at`` (when present)
        then primary key, so pages are stable."""
        order = [getattr(cls, "created_at")] if hasattr(cls, "created_at") else []
        order += list(sa.inspect(cls).primary_key)
        pagination = cls._db().paginate(
            sa.select(cls).order_by(*order),
            page=page,
            per_page=per_page,
            error_out=False,
        )
        return {
            "items": pagination.items,
            "total": pagination.total or 0,
            "pages": pagination.pages,
            "page": pagination.page,
            "per_page": pagination.per_page,
        }


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, (uuid.UUID, Decimal)):
        return str(value)
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def hidden_column(*args: Any, **kwargs: Any) -> Any:
    """A ``mapped_column`` that ``to_dict()`` never serialises.

    Takes the same arguments as ``db.Column``/``mapped_column``::

        password_hash = hidden_column(db.String(200))

    Equivalent to passing ``info={"hidden": True}``, which also works on
    ``db.Column``, ``mapped_column`` and ``db.relationship``.
    """
    info = dict(kwargs.pop("info", None) or {})
    info["hidden"] = True
    return mapped_column(*args, info=info, **kwargs)


_hidden_cache: weakref.WeakKeyDictionary[type, frozenset[str]] = weakref.WeakKeyDictionary()


def _hidden_keys(cls: type) -> frozenset[str]:
    """Attribute names on ``cls`` marked ``info={"hidden": True}``."""
    keys = _hidden_cache.get(cls)
    if keys is None:
        mapper = sa.inspect(cls)
        found = set()
        for attr in mapper.column_attrs:
            if attr.info.get("hidden") or any(c.info.get("hidden") for c in attr.columns):
                found.add(attr.key)
        for rel in mapper.relationships:
            if rel.info.get("hidden"):
                found.add(rel.key)
        keys = _hidden_cache[cls] = frozenset(found)
    return keys


class SerializerMixin:
    """``to_dict()`` with hidden fields, depth control and cycle safety."""

    #: Never serialised, at any depth. Use for secrets such as password hashes.
    #: Columns can instead be marked with ``hidden_column(...)`` or
    #: ``info={"hidden": True}``; both mechanisms are combined.
    __hidden_fields__: ClassVar[frozenset[str]] = frozenset()

    def to_dict(
        self,
        depth: int | None = 1,
        exclude: Iterable[str] = (),
        json_safe: bool = False,
        _seen: set[int] | None = None,
    ) -> dict[str, Any]:
        """
        Dictionary of column values and related objects.

        Args:
            depth: How many relationship levels to follow. ``0`` returns
                columns only, ``None`` follows every level. Objects already
                serialised higher in the tree are skipped, so bidirectional
                relationships never recurse forever.
            exclude: Extra field names to leave out of this object.
            json_safe: Convert datetimes/dates to ISO strings, UUIDs and
                Decimals to ``str`` and enums to their value, so the result
                can go straight to ``jsonify``.
        """
        skip = set(exclude) | self.__hidden_fields__ | _hidden_keys(type(self))
        seen = set() if _seen is None else _seen
        seen.add(id(self))
        mapper = sa.inspect(type(self))

        data: dict[str, Any] = {}
        for attr in mapper.column_attrs:
            if attr.key not in skip:
                value = getattr(self, attr.key)
                data[attr.key] = _json_safe(value) if json_safe else value

        if depth is not None and depth <= 0:
            return data
        child_depth = None if depth is None else depth - 1

        def dump(obj: Any) -> dict[str, Any]:
            return obj.to_dict(depth=child_depth, json_safe=json_safe, _seen=seen)

        for rel in mapper.relationships:
            if rel.key in skip:
                continue
            value = getattr(self, rel.key)
            if value is None:
                data[rel.key] = None
            elif rel.uselist:
                data[rel.key] = [dump(o) for o in value if id(o) not in seen]
            elif id(value) not in seen:
                data[rel.key] = dump(value)
        return data


# ---------------------------------------------------------------------------
# Batteries-included combination
# ---------------------------------------------------------------------------


class BaseModelMixin(UUIDMixin, TimestampMixin, CRUDMixin, SerializerMixin):
    """UUID key + timestamps + CRUD/query helpers + ``to_dict()``."""
