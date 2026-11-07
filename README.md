# FlaskSQLAlchemyBaseModel

[![Tests](https://github.com/AnozieChibuike/FlaskSQLAlchemyBaseModel/actions/workflows/tests.yml/badge.svg)](https://github.com/AnozieChibuike/FlaskSQLAlchemyBaseModel/actions/workflows/tests.yml)
[![PyPI](https://img.shields.io/pypi/v/FlaskSQLAlchemyBaseModel)](https://pypi.org/project/FlaskSQLAlchemyBaseModel/)

Composable model mixins for Flask-SQLAlchemy.

Most Flask projects end up writing the same base model: a UUID primary key, `created_at`/`updated_at`, `save()`, `to_dict()`, maybe soft delete. Each copy has its own subtle bugs. This package gives you those pieces as small mixins that you combine per model. The edge cases are handled and tested.

```python
class Post(UUIDMixin, TimestampMixin, SoftDeleteMixin, CRUDMixin, SerializerMixin, db.Model):
    title = db.Column(db.String(200), nullable=False)
```

## Features

- **Pick what you need.** UUID or integer keys, timestamps, soft delete, CRUD helpers and serialisation are separate mixins. `BaseModelMixin` bundles the common set.
- **Soft delete that actually hides rows.** Deleted rows are filtered out of *every* ORM query: helpers, `Model.query`, `db.select()`, `session.get()` and relationship loads.
- **Safe updates.** `update(request.json)` only sets mapped columns and never touches `id`, timestamps or any field you protect.
- **Safe serialisation.** `to_dict()` never outputs hidden fields (such as password hashes), limits relationship depth, never loops on `back_populates`, and returns JSON-ready output on request.
- **Efficient queries.** Counts and existence checks run in SQL. Pagination is stably ordered.
- **Migration-friendly.** Defaults are generated in Python, so Flask-Migrate/Alembic produces clean migrations with no spurious diffs.
- **Typed.** Ships `py.typed`, and class methods return your model type.
- **Works with your own `db`.** No global `SQLAlchemy()` is forced on you.

Requires Python 3.10+, Flask 3, Flask-SQLAlchemy 3.1+ and SQLAlchemy 2.0.16+.

## Install

```bash
pip install FlaskSQLAlchemyBaseModel
```

## Quick start

```python
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flasksqlalchemybasemodel import BaseModelMixin

db = SQLAlchemy()


class User(BaseModelMixin, db.Model):          # mixins go before db.Model
    __hidden_fields__ = frozenset({"password_hash"})

    name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200))


app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"
db.init_app(app)


@app.post("/users")
def create_user():
    data = request.json
    user = User.create(name=data["name"], email=data["email"])
    return jsonify(user.to_dict(json_safe=True)), 201


@app.patch("/users/<id>")
def update_user(id):
    user = User.get_or_404(id)
    user.update(request.json)                   # id/timestamps can't be overwritten
    return jsonify(user.to_dict(json_safe=True))


@app.get("/users")
def list_users():
    page = User.paginate(page=request.args.get("page", 1, type=int), per_page=20)
    page["items"] = [u.to_dict(json_safe=True) for u in page["items"]]
    return jsonify(page)
```

Don't have a `db` yet? Use the bundled one:

```python
from flasksqlalchemybasemodel import db, BaseModel

class User(BaseModel):
    name = db.Column(db.String(50))
```

## Documentation

| Guide | |
|---|---|
| [Mixins](docs/mixins.md) | Every mixin, how to combine them, and the one ordering rule |
| [CRUD & queries](docs/crud-and-queries.md) | `create`, `save`, `update`, `get`, filters, counts, pagination, transactions |
| [Serialisation](docs/serialization.md) | `to_dict()`, hidden fields, depth, JSON output |
| [Soft delete](docs/soft-delete.md) | How rows are hidden, including deleted rows, restoring |
| [Migrations](docs/migrations.md) | Flask-Migrate/Alembic, adding mixins to existing tables |

## Development

```bash
pip install -e . pytest alembic
pytest
```

CI runs the suite on Python 3.10–3.13 and against the minimum supported dependency versions.

## License

MIT
