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

Fields listed in `__hidden_fields__` are **never** serialised: not at any depth, and not when the object appears inside another object's relationships.

```python
class User(BaseModelMixin, db.Model):
    __hidden_fields__ = frozenset({"password_hash", "api_key"})
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
