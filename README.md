# flask-modelkit

[![Tests](https://github.com/AnozieChibuike/FlaskModelKit/actions/workflows/tests.yml/badge.svg)](https://github.com/AnozieChibuike/FlaskModelKit/actions/workflows/tests.yml)
[![PyPI](https://img.shields.io/pypi/v/flask-modelkit?label=pypi)](https://pypi.org/project/flask-modelkit/)
[![Docs](https://img.shields.io/badge/docs-flask--modelkit-A84E08)](https://anoziechibuike.github.io/FlaskModelKit/)
[![Python](https://img.shields.io/pypi/pyversions/flask-modelkit?label=python)](https://pypi.org/project/flask-modelkit/)
[![Downloads/month](https://img.shields.io/pypi/dm/flask-modelkit)](https://pypistats.org/packages/flask-modelkit)
[![Total downloads](https://img.shields.io/pepy/dt/flask-modelkit)](https://pepy.tech/projects/flask-modelkit)
[![GitHub stars](https://img.shields.io/github/stars/AnozieChibuike/FlaskModelKit?style=flat&logo=github)](https://github.com/AnozieChibuike/FlaskModelKit/stargazers)
[![License: MIT](https://img.shields.io/github/license/AnozieChibuike/FlaskModelKit)](https://github.com/AnozieChibuike/FlaskModelKit/blob/master/LICENSE)

Composable model mixins for Flask-SQLAlchemy.

**Documentation: [anoziechibuike.github.io/FlaskModelKit](https://anoziechibuike.github.io/FlaskModelKit/)**

⭐ If flask-modelkit saves you from writing another base model, [star it on GitHub](https://github.com/AnozieChibuike/FlaskModelKit). It helps other Flask developers find it.

> Formerly published as `FlaskSQLAlchemyBaseModel`. See [Migrating from FlaskSQLAlchemyBaseModel](#migrating-from-flasksqlalchemybasemodel).

Most Flask projects end up writing the same base model: a UUID primary key, `created_at`/`updated_at`, `save()`, `to_dict()`, maybe soft delete. Each copy has its own subtle bugs. This package gives you those pieces as small mixins that you combine per model. The edge cases are handled and tested.

```python
class Post(UUIDMixin, TimestampMixin, SoftDeleteMixin, CRUDMixin, SerializerMixin, db.Model):
    title = db.Column(db.String(200), nullable=False)
```

## Features

- **Pick what you need.** UUID or integer keys, timestamps, soft delete, CRUD helpers and serialisation are separate mixins. `BaseModelMixin` bundles the common set.
- **Soft delete that actually hides rows.** Deleted rows are filtered out of *every* ORM query: helpers, `Model.query`, `db.select()`, `session.get()` and relationship loads.
- **Hidden and protected fields.** Mark a column `hidden` (never sent to the client), `protected` (never set from client input) or both, right where you declare it.
- **Safe updates.** `update(request.json)` only sets mapped columns and never touches `id`, timestamps or any protected field.
- **Create from request data in one line.** `create_or_abort(request.json)` drops unsafe keys, answers 400 naming every missing field, and 409 naming a duplicate unique field.
- **Safe serialisation.** `to_dict()` never outputs hidden fields (such as password hashes), limits relationship depth, never loops on `back_populates`, and returns JSON-ready output on request.
- **Efficient queries.** Counts and existence checks run in SQL. Pagination is stably ordered.
- **Migration-friendly.** Defaults are generated in Python, so Flask-Migrate/Alembic produces clean migrations with no spurious diffs.
- **Typed.** Ships `py.typed`, and class methods return your model type.
- **Works with your own `db`.** No global `SQLAlchemy()` is forced on you.

Requires Python 3.10+, Flask 3, Flask-SQLAlchemy 3.1+ and SQLAlchemy 2.0.16+.

## Install

```bash
pip install flask-modelkit
```

## Quick start

```python
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_modelkit import BaseModelMixin, protected_column, secret_column

db = SQLAlchemy()


class User(BaseModelMixin, db.Model):          # mixins go before db.Model
    name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    is_admin = protected_column(db.Boolean, default=False)   # input can't set it
    password_hash = secret_column(db.String(200))            # never read out, never written in


app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"
db.init_app(app)

with app.app_context():
    db.create_all()                             # or Flask-Migrate, see https://anoziechibuike.github.io/FlaskModelKit/#migrations


@app.post("/users")
def create_user():
    # 400 if name/email are missing, 409 if the email is taken, unknown keys dropped
    user = User.create_or_abort(request.get_json(silent=True))
    return jsonify(user.to_dict(json_safe=True)), 201


@app.patch("/users/<id>")
def update_user(id):
    user = User.get_or_404(id)
    user.update(request.json)                   # id, timestamps, is_admin, password_hash can't be set
    return jsonify(user.to_dict(json_safe=True))


@app.get("/users")
def list_users():
    page = User.paginate(page=request.args.get("page", 1, type=int), per_page=20)
    page["items"] = [u.to_dict(json_safe=True) for u in page["items"]]
    return jsonify(page)
```

Don't have a `db` yet? Use the bundled one:

```python
from flask_modelkit import db, BaseModel

class User(BaseModel):
    name = db.Column(db.String(50))
```

## Documentation

The full documentation is at **[anoziechibuike.github.io/FlaskModelKit](https://anoziechibuike.github.io/FlaskModelKit/)**.

| Guide | |
|---|---|
| [Quick start](https://anoziechibuike.github.io/FlaskModelKit/#quick-start) | A complete app in four steps |
| [Mixins](https://anoziechibuike.github.io/FlaskModelKit/#mixins) | Every mixin, an interactive builder, and the one ordering rule |
| [Creating & updating](https://anoziechibuike.github.io/FlaskModelKit/#writing) | `create`, `create_or_abort`, `save`, `update`, transactions |
| [Reading & filtering](https://anoziechibuike.github.io/FlaskModelKit/#reading) | `get`, filters, counts, pagination, custom queries |
| [Hidden vs protected](https://anoziechibuike.github.io/FlaskModelKit/#hidden-vs-protected) | Controlling what goes out to and comes in from the client |
| [Serialisation](https://anoziechibuike.github.io/FlaskModelKit/#serialization) | `to_dict()`, depth, JSON output |
| [Soft delete](https://anoziechibuike.github.io/FlaskModelKit/#soft-delete) | How rows are hidden, including deleted rows, restoring |
| [Migrations](https://anoziechibuike.github.io/FlaskModelKit/#migrations) | Flask-Migrate/Alembic, adding mixins to existing tables |
| [Project examples](https://anoziechibuike.github.io/FlaskModelKit/#example-blog) | A blog API, a shop checkout, lookup tables |
| [API reference](https://anoziechibuike.github.io/FlaskModelKit/#api-reference) | Every public name |

## Use with AI agents

AI coding assistants don't know this package's rules: mixins before `db.Model`, `create_or_abort()` for request data, `secret_column()` for password hashes. [`AGENT.md`](https://anoziechibuike.github.io/FlaskModelKit/AGENT.md) spells them out. Add it to your project once, from the project root:

```bash
# Claude Code: save it, then import it from CLAUDE.md
mkdir -p .claude && curl -fsSL https://anoziechibuike.github.io/FlaskModelKit/AGENT.md -o .claude/flask-modelkit.md
echo "@.claude/flask-modelkit.md" >> CLAUDE.md

# Cursor: a project rule attached to Python files
mkdir -p .cursor/rules
{ printf -- '---\ndescription: How to use flask-modelkit models, fields and endpoints\nglobs: **/*.py\nalwaysApply: false\n---\n\n'
  curl -fsSL https://anoziechibuike.github.io/FlaskModelKit/AGENT.md; } > .cursor/rules/flask-modelkit.mdc

# GitHub Copilot: path-specific instructions for Python files
mkdir -p .github/instructions
{ printf -- '---\napplyTo: "**/*.py"\n---\n\n'
  curl -fsSL https://anoziechibuike.github.io/FlaskModelKit/AGENT.md; } > .github/instructions/flask-modelkit.instructions.md

# Codex, Jules, Amp, Zed and other AGENTS.md readers (Gemini CLI: GEMINI.md)
curl -fsSL https://anoziechibuike.github.io/FlaskModelKit/AGENT.md >> AGENTS.md
```

In a chat assistant, say: *"Read https://anoziechibuike.github.io/FlaskModelKit/AGENT.md and follow it for all flask-modelkit code."* To pin the rules to your installed version, download from the release tag instead, for example `https://raw.githubusercontent.com/AnozieChibuike/FlaskModelKit/v1.0.0/AGENT.md`. See [Use with AI agents](https://anoziechibuike.github.io/FlaskModelKit/#ai-agents) for details.

## Migrating from FlaskSQLAlchemyBaseModel

`flask-modelkit` 1.0 continues `FlaskSQLAlchemyBaseModel` under a new name.

```bash
pip uninstall FlaskSQLAlchemyBaseModel
pip install flask-modelkit
```

Then replace the import:

```python
# before
from flasksqlalchemybasemodel import BaseModel, db
# after
from flask_modelkit import BaseModel, db
```

The old `flasksqlalchemybasemodel.src` module is gone; import from `flask_modelkit` directly. The columns the mixins create are unchanged, so no database migration is needed. See [CHANGELOG.md](CHANGELOG.md) for everything else that changed.

## Development

```bash
pip install -e . pytest alembic
pytest
```

CI runs the suite on Python 3.10–3.13 and against the minimum supported dependency versions.

## Star history

<a href="https://star-history.com/#AnozieChibuike/FlaskModelKit&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=AnozieChibuike/FlaskModelKit&type=Date&theme=dark">
    <img alt="flask-modelkit star history" src="https://api.star-history.com/svg?repos=AnozieChibuike/FlaskModelKit&type=Date" width="600">
  </picture>
</a>

More numbers, including downloads, live on the [Community & stats](https://anoziechibuike.github.io/FlaskModelKit/#community) page.

## License

MIT
