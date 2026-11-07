# Changelog

## flask-modelkit 1.0.0

First release under the new name. This package continues
`FlaskSQLAlchemyBaseModel` (last release 1.2.0). Install with
`pip install flask-modelkit` and import from `flask_modelkit`.

### Added

- Separate mixins: `UUIDMixin`, `IntIdMixin`, `TimestampMixin`,
  `SoftDeleteMixin`, `CRUDMixin`, `SerializerMixin`, combined in
  `BaseModelMixin`. They work with your own `SQLAlchemy()` instance.
- `SoftDeleteMixin`: `soft_delete()`, `restore()`, `is_deleted`. Deleted rows
  are hidden from every ORM query, including `db.session.get()` and
  relationship loads.
- `create_or_abort()`: create from request data. Drops unknown and protected
  keys, raises `MissingFieldsError` (400) naming missing fields and
  `DuplicateValueError` (409) naming taken unique fields, both as JSON.
- `__protected_fields__`: fields `update()` and `create_or_abort()` never set.
- Hidden fields: `hidden_column()`, `info={"hidden": True}` and
  `__hidden_fields__` keep values such as password hashes out of `to_dict()`.
- `to_dict(depth=, exclude=, json_safe=)`.
- `select()`, a starting point for custom queries.
- `commit=False` on every write method, for grouping changes in one transaction.
- `py.typed`; class methods return your model type.

### Changed

- Timestamps are now **UTC**. 1.2 used the server's local time
  (`datetime.now()`). Existing rows keep their old values.
- `update()` only sets mapped columns and relationships. 1.2 set any attribute,
  including `id` and method names.
- `updated_at` is refreshed on every UPDATE, including a plain
  `db.session.commit()`.
- `to_dict()` no longer recurses forever on two-way relationships and follows
  one level of relationships by default.
- `get_or_404()` says `"<Model> not found"` instead of
  `"Item with given ID not found"`.
- `paginate()` has a stable order (`created_at`, then primary key).
- `count_all()` and `exists()` run as SQL `COUNT`/`EXISTS`. In 1.2,
  `count_all()` loaded every row into Python.

### Removed

- The `flasksqlalchemybasemodel.src` module. Import from `flask_modelkit`.

The columns created by the mixins (`id String(126)`, `created_at`,
`updated_at`) are the same as in 1.2, so existing tables need no migration.
