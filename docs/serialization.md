# Serialisation

Provided by `SerializerMixin` (included in `BaseModelMixin`).

```python
user.to_dict()
# {"id": "…", "created_at": datetime(…), "updated_at": datetime(…),
#  "name": "Ada", "posts": [{…}, {…}]}
```

## Signature

```python
to_dict(depth=1, exclude=(), json_safe=False)
```

| Argument | Meaning |
|---|---|
| `depth` | Relationship levels to follow. `0` returns columns only, `1` (the default) includes direct relationships, and `None` follows every level. |
| `exclude` | Field names to leave out of this object. |
| `json_safe` | Converts values so the result can go straight into `jsonify()`, as below. |

`json_safe=True` converts:

| Python value | JSON value |
|---|---|
| `datetime`, `date`, `time` | ISO 8601 string |
| `Decimal`, `UUID` | string (no precision lost) |
| `Enum` | its `.value` |
| `bytes` | UTF-8 string |

```python
return jsonify(user.to_dict(json_safe=True))
```

## Hidden fields

Hidden fields are **never** serialised: not at any depth, and not when the object appears inside another object's relationships. The value is still stored and readable on the object; it is only left out of `to_dict()`.

Mark a column hidden where you declare it:

```python
from flask_modelkit import BaseModelMixin, hidden_column

class User(BaseModelMixin, db.Model):
    name = db.Column(db.String(50))
    password_hash = hidden_column(db.String(200))                 # shorthand
    api_key = db.Column(db.String(64), info={"hidden": True})      # same thing
    audit_log = db.relationship("AuditEntry", info={"hidden": True})
```

`hidden_column()` takes the same arguments as `db.Column`. It is shorthand for `info={"hidden": True}`, which is SQLAlchemy's own metadata slot and works on `db.Column`, `mapped_column` and `db.relationship`.

You can also list names in `__hidden_fields__`, for example to hide a column inherited from a mixin. Both ways are combined:

```python
class User(BaseModelMixin, db.Model):
    __hidden_fields__ = frozenset({"updated_at"})
```

Use hidden fields for secrets. Use `exclude=` for fields you don't need in one particular response.

## Relationships and cycles

Two-way relationships (`back_populates` or `backref`) are safe at any depth. An object already serialised higher up the tree is skipped instead of serialised again:

```python
author.to_dict(depth=None)
# {"name": "A", "books": [{"title": "B", "chapters": [{"title": "C"}]}]}
#                          ^ no "author" key here, so no infinite loop
```

Keep `depth` low on list endpoints. Each relationship level can mean another query per row. For large lists, either set `depth=0` and add what you need yourself, or load the relationships eagerly with `selectinload`:

```python
from sqlalchemy.orm import selectinload

stmt = Author.select().options(selectinload(Author.books))
authors = db.session.scalars(stmt).all()
data = [a.to_dict() for a in authors]   # no extra queries for books
```

On models with `SoftDeleteMixin`, soft-deleted related objects are left out automatically.
