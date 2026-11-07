# Soft delete

`SoftDeleteMixin` marks rows as deleted instead of removing them, so they can be restored, audited, or kept to satisfy foreign keys.

```python
class Post(SoftDeleteMixin, BaseModelMixin, db.Model):
    title = db.Column(db.String(200))

post.soft_delete()     # sets deleted_at = now (UTC) and commits
post.is_deleted        # True
post.restore()         # deleted_at = None
post.delete()          # hard delete: the row is really removed
```

`soft_delete()` and `restore()` accept `commit=False`, like the other write methods.

## Deleted rows are hidden everywhere

Most soft-delete implementations only filter their own helper methods, so one raw query leaks deleted data. This mixin hooks into the SQLAlchemy session instead, so soft-deleted rows are left out of **every ORM query** on the model:

```python
Post.all()                               # hidden
Post.get(id), Post.filter_one(...)       # hidden
Post.count_all(), Post.exists(...)       # hidden
Post.query.filter_by(...).all()          # hidden
db.session.scalars(db.select(Post))      # hidden
db.session.get(Post, id)                 # hidden
author.posts                             # hidden in relationship loads too
```

## Including deleted rows

Add the `include_deleted` execution option to a statement:

```python
Post.get(id, include_deleted=True)

stmt = Post.select(include_deleted=True)               # same as below
stmt = db.select(Post).execution_options(include_deleted=True)

trash = db.session.scalars(
    Post.select(include_deleted=True).where(Post.deleted_at.is_not(None))
).all()
```

To restore a row, load it with `include_deleted=True` first:

```python
post = Post.get(id, include_deleted=True)
post.restore()
```

## Things to know

- **`update()` can't undo a deletion.** `deleted_at` is a protected field, so `post.update(request.json)` can never undelete a post.
- **Unique constraints still see deleted rows.** If `email` is unique and a user is soft-deleted, a new user with the same email will fail. `create_or_abort()` reports this as a 409 on `email`, like any other duplicate. To let the email be reused, use a partial unique index (`WHERE deleted_at IS NULL`) on PostgreSQL, or include `deleted_at` in the constraint.
- **Core SQL is not filtered.** Only ORM queries are filtered. Statements built on `Post.__table__` and raw `text()` SQL see all rows.
- **Bulk operations.** `db.session.execute(update(Post)...)` and `delete(Post)` are not filtered. Add `.where(Post.deleted_at.is_(None))` yourself.
