# flask-modelkit: instructions for AI coding agents

This project uses **flask-modelkit**, composable model mixins for Flask-SQLAlchemy.
Follow these rules when you write or change models, endpoints or queries.
Full docs: https://anoziechibuike.github.io/FlaskModelKit/

- Package: `pip install flask-modelkit` · import: `from flask_modelkit import ...`
- Requires Python 3.10+, Flask 3, Flask-SQLAlchemy 3.1+, SQLAlchemy 2.0.16+.
- The PyPI name was formerly `FlaskSQLAlchemyBaseModel`, and the import was `flasksqlalchemybasemodel`. Never use those names in new code.

## Rules

1. **Mixins go before `db.Model`.** `class Post(BaseModelMixin, db.Model)`, never `class Post(db.Model, BaseModelMixin)`. The wrong order skips the mixin constructors, so `id` and the timestamps are missing until flush.
2. **Never pass request data to `create()`.** `Model.create(**request.json)` is a mass-assignment hole. Use `Model.create_or_abort(request.get_json(silent=True), ...)` for request data. `create()` is for trusted values only.
3. **`update(request.json)` is safe; plain assignment is not filtered.** `obj.update(data)` ignores unknown and protected keys. `setattr`/`obj.x = data["x"]` is only for values your code controls.
4. **Secrets use `secret_column()`.** Password hashes, API keys, tokens and reset codes: `password_hash = secret_column(db.String(255), nullable=False)`. Never use `hidden_column()` for a secret, because hidden only stops output and clients could still *set* it.
5. **Permission, ownership and server-computed fields use `protected_column()`.** Examples: `is_admin`, `role`, `email_verified`, `author_id`, `owner_id`, `total`, `balance`. For ownership, also protect the relationship: `db.relationship(..., info={"protected": True})`.
6. **Protected, required fields are passed as keyword arguments.** `Post.create_or_abort(data, author=current_user)` or `User.create_or_abort(data, password_hash=hash_)`. Keyword arguments are trusted and override `data`. If you forget one, `create_or_abort()` raises `TypeError: ... can never be filled`. Fix the call; don't catch the error.
7. **Don't add your own `id`, `created_at`, `updated_at` or `deleted_at` columns** to models that use the matching mixins. They already exist, are protected, and are set automatically.
8. **Timestamps are naive UTC.** Compare with `flask_modelkit.utcnow()`, never `datetime.now()` or `datetime.utcnow()`.
9. **Return JSON with `to_dict(json_safe=True)`.** Never build response dicts by hand from `__dict__` or `__table__.columns`, because that leaks hidden fields.
10. **Use the helpers' built-in errors.** Don't hand-write 400/404/409 checks that the helpers already do: `get_or_404()` returns 404, `create_or_abort()` returns 400 naming missing fields and 409 naming duplicate unique fields.

## Choosing mixins

| Need | Bases |
|---|---|
| Default model | `BaseModelMixin, db.Model` (UUID `id` + timestamps + CRUD + `to_dict`) |
| Default + soft delete | `SoftDeleteMixin, BaseModelMixin, db.Model` |
| Integer key, no timestamps (lookup tables) | `IntIdMixin, CRUDMixin, SerializerMixin, db.Model` |
| Columns only, plain `db.session` | `UUIDMixin, TimestampMixin, db.Model` |
| Project-wide base | `class Model(SoftDeleteMixin, BaseModelMixin, db.Model): __abstract__ = True` |

Use one primary-key mixin per model (`UUIDMixin` or `IntIdMixin`). A foreign key to a UUID model is `db.String(126)`.

## Field access: hidden vs protected

| Field | Declare with | Clients see it | Clients set it |
|---|---|---|---|
| Ordinary data (`name`, `bio`, `title`) | `db.Column(...)` | yes | yes |
| Permissions, ownership, computed (`is_admin`, `author_id`, `total`) | `protected_column(...)` | yes | **no** |
| Write-only input (a webhook secret the user pastes in) | `hidden_column(...)` | **no** | yes |
| Secrets, server-only data (`password_hash`, `api_key`, `fraud_score`) | `secret_column(...)` | **no** | **no** |

- `hidden_column`, `protected_column` and `secret_column` take the same arguments as `db.Column`, including `db.ForeignKey(...)`.
- On relationships, or to keep `db.Column`, use `info={"hidden": True}` and/or `info={"protected": True}`.
- For fields you don't declare, such as inherited ones, extend the class set, keeping the defaults: `__protected_fields__ = BaseModelMixin.__protected_fields__ | {"tenant_id"}`. Never replace it with a bare `frozenset({...})`, because that unprotects `id` and the timestamps.
- `Model.protected_fields()` returns the full protected set.
- "Set at signup, read-only afterwards" (such as `email`): **don't** protect it. Filter profile updates with an allowlist instead: `user.update({k: v for k, v in data.items() if k in {"name", "bio"}})`.

## Endpoint patterns

```python
from flask import jsonify, request
from werkzeug.security import generate_password_hash

@app.post("/users")
def register():
    data = request.get_json(silent=True) or {}
    pw = data.get("password")
    user = User.create_or_abort(
        data,
        required=["password"],                                  # input that isn't a column
        password_hash=generate_password_hash(pw) if pw else None,  # trusted value
    )
    return jsonify(user.to_dict(json_safe=True)), 201

@app.post("/posts")
def create_post():
    post = Post.create_or_abort(request.get_json(silent=True), author=current_user)
    return jsonify(post.to_dict(json_safe=True)), 201

@app.patch("/posts/<id>")
def edit_post(id):
    post = Post.get_or_404(id)
    post.update(request.get_json(silent=True) or {})
    return jsonify(post.to_dict(json_safe=True))

@app.get("/posts")
def list_posts():
    page = Post.paginate(page=request.args.get("page", 1, type=int), per_page=20)
    page["items"] = [p.to_dict(depth=0, json_safe=True) for p in page["items"]]
    return jsonify(page)
```

- `create_or_abort(data, fields=[...])` accepts only the listed keys from `data`.
- Errors render as JSON automatically: `{"error": "missing_fields" | "duplicate" | "invalid_body", "message": ..., "fields": [...]}`. To customise, register `@app.errorhandler(MissingFieldsError)`; the field names are on `e.fields`.
- `create_or_abort()` does not validate types or formats. Validate with marshmallow or pydantic first, then pass the validated dict in.

## Queries

- `Model.get(id)` returns the object or `None`, and `Model.get_or_404(id)` aborts with 404.
- `filter_one(**f)` and `filter_all(**f)` take exact-match `column=value` pairs, combined with AND.
- `exists(**f)`, `count_all()` and `filter_and_count_all(**f)` run in SQL. Use them instead of `len(Model.all())`.
- `paginate(page, per_page)` takes no filters. For filtered or sorted pages, use `db.paginate(Model.select().where(...).order_by(...), page=..., per_page=...)`.
- For ranges, `OR`, `LIKE` or joins, start from `Model.select()` and run it with `db.session.scalars(stmt)`.

## Soft delete (`SoftDeleteMixin`)

- `obj.soft_delete()` hides the row, `obj.restore()` brings it back, and `obj.is_deleted` reports which.
- `obj.delete()` is a **hard** delete, even on soft-delete models.
- Deleted rows are hidden from **every** ORM query automatically: helpers, `Model.query`, `db.select()`, `db.session.get()` and relationship loads. Don't add `.where(Model.deleted_at.is_(None))` to ORM queries.
- To include deleted rows, use `Model.select(include_deleted=True)`, `Model.get(id, include_deleted=True)`, or `.execution_options(include_deleted=True)`.
- Bulk `update()`/`delete()` statements and raw SQL are **not** filtered. Add the `deleted_at` condition yourself there.
- Unique constraints still see deleted rows. Use a partial unique index if values must be reusable.

## Serialisation

- `to_dict(depth=1, exclude=(), json_safe=False)`: `depth=0` returns columns only, and `depth=None` follows every level. It is safe on `back_populates` cycles.
- Hidden fields are never output, at any depth. Use `exclude=[...]` for one-off omissions.
- For list endpoints, use `depth=0`, or eager-load with `selectinload` to avoid N+1 queries.

## Transactions

- Every write method (`create`, `create_or_abort`, `save`, `update`, `delete`, `soft_delete`, `restore`) commits by default. Pass `commit=False` to several of them, then call `db.session.commit()` once for all-or-nothing writes.
- After an `IntegrityError` from `save()`/`update()`, call `db.session.rollback()` before using the session again. `create_or_abort()` rolls back for you.

## Migrations

- Use Flask-Migrate/Alembic as normal. Defaults are Python-side, so autogenerate produces no spurious diffs.
- When adding `TimestampMixin` to a table that already has rows, give `created_at`/`updated_at` a temporary `server_default=sa.func.current_timestamp()` in the migration, then remove it.
- `SoftDeleteMixin` adds a nullable, indexed `deleted_at`, so the generated migration works as is.
