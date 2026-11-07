# Mixins

Every feature is a separate mixin. Combine the ones a model needs.

```python
from flask_modelkit import (
    UUIDMixin, IntIdMixin, TimestampMixin, SoftDeleteMixin,
    CRUDMixin, SerializerMixin, BaseModelMixin,
)
```

| Mixin | Adds |
|---|---|
| `UUIDMixin` | `id`: UUID4 string primary key, set when the object is constructed |
| `IntIdMixin` | `id`: auto-increment integer primary key, set by the database on insert |
| `TimestampMixin` | `created_at`, `updated_at`: UTC timestamps |
| `SoftDeleteMixin` | `deleted_at`, `soft_delete()`, `restore()`, `is_deleted`; hides deleted rows ([guide](soft-delete.md)) |
| `CRUDMixin` | `create`, `create_or_abort`, `save`, `update`, `delete`, `get`, filters, counts, `paginate` ([guide](crud-and-queries.md)) |
| `SerializerMixin` | `to_dict()` ([guide](serialization.md)) |
| `BaseModelMixin` | `UUIDMixin` + `TimestampMixin` + `CRUDMixin` + `SerializerMixin` |

## The one rule: mixins before `db.Model`

```python
class Post(BaseModelMixin, db.Model):   # correct
class Post(db.Model, BaseModelMixin):   # wrong
```

Python runs the constructors of the base classes in order, and SQLAlchemy's constructor doesn't call the next one in line. With the mixins first, `UUIDMixin` and `TimestampMixin` can fill in `id` and the timestamps as soon as you construct the object:

```python
post = Post(title="Hello")
post.id          # '3f2b…', already usable (e.g. in a URL) before saving
```

The order *among* the mixins doesn't matter.

## Recipes

**Default:** UUID key, timestamps, helpers, serialisation.

```python
class User(BaseModelMixin, db.Model):
    email = db.Column(db.String(100), unique=True, nullable=False)
```

**Soft-deletable content**

```python
class Post(SoftDeleteMixin, BaseModelMixin, db.Model):
    title = db.Column(db.String(200))
```

**Integer keys, no timestamps.** Useful for lookup tables:

```python
class Country(IntIdMixin, CRUDMixin, SerializerMixin, db.Model):
    code = db.Column(db.String(2), unique=True)
```

**Columns only, no helpers.** Useful if you prefer plain `db.session` calls:

```python
class AuditLog(UUIDMixin, TimestampMixin, db.Model):
    action = db.Column(db.String(50))
```

**A project-wide base class**

```python
class Model(SoftDeleteMixin, BaseModelMixin, db.Model):
    __abstract__ = True

class Invoice(Model):
    amount = db.Column(db.Numeric(10, 2))
```

## Column details

| Column | Type | Notes |
|---|---|---|
| `id` (UUID) | `String(126)` | Generated in Python. Pass `id=...` to set it yourself. |
| `id` (int) | `Integer` | Autoincrement. `None` until the first flush. |
| `created_at` | `DateTime`, not null | UTC, naive. Set on construction. |
| `updated_at` | `DateTime`, not null | UTC, naive. Refreshed on every UPDATE, including plain `db.session.commit()`. |
| `deleted_at` | `DateTime`, nullable, indexed | `NULL` while the row is live. |

Timestamps are stored as *naive* UTC datetimes, so they behave the same on SQLite, PostgreSQL and MySQL. Use `flask_modelkit.utcnow()` when comparing against them.

## Using the bundled `db`

If your app doesn't have a `SQLAlchemy()` instance yet, the package provides one with a ready-made abstract `BaseModel` (equivalent to `BaseModelMixin`):

```python
from flask_modelkit import db, BaseModel

class User(BaseModel):
    name = db.Column(db.String(50))

db.init_app(app)
```
