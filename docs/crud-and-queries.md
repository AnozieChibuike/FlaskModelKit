# CRUD & queries

Provided by `CRUDMixin` (included in `BaseModelMixin`). All methods must run inside an application context.

## Writing

```python
user = User.create(name="Ada", email="ada@example.com")   # construct + save

user.name = "Ada L."
user.save()

user.update({"name": "Ada Lovelace"})                     # set + save
user.delete()                                             # removes the row
```

### `update()` is safe for request data

`update()` only sets attributes that are mapped columns or relationships. It silently ignores:

- unknown keys (`{"nonsense": 1}`) and method names (`{"save": "x"}`)
- protected fields: `id`, `created_at`, `updated_at` and `deleted_at`

So passing `request.json` directly can't change a primary key or forge a timestamp. To protect more fields, extend the set:

```python
class User(BaseModelMixin, db.Model):
    __protected_fields__ = BaseModelMixin.__protected_fields__ | {"is_admin", "email_verified"}
```

Protection only applies to `update()`. Plain assignment (`user.is_admin = True`) and `create(...)` still work for trusted code. Don't pass raw request data to `create(**request.json)`: name the fields you accept.

### Transactions

`create`, `save`, `update`, `delete`, `soft_delete` and `restore` all commit by default. Pass `commit=False` to group several changes into one transaction:

```python
order = Order.create(user=user, commit=False)
for item in cart:
    OrderLine.create(order=order, product=item, commit=False)
db.session.commit()          # all or nothing
```

## Reading

| Method | Returns |
|---|---|
| `Model.get(id)` | object or `None` |
| `Model.get_or_404(id)` | object, or aborts the request with 404 |
| `Model.all()` | `list[Model]` |
| `Model.filter_one(**filters)` | first match or `None` |
| `Model.filter_all(**filters)` | `list[Model]` |
| `Model.exists(**filters)` | `bool` (SQL `EXISTS`) |
| `Model.count_all()` | `int` (SQL `COUNT`) |
| `Model.filter_and_count_all(**filters)` | `int` (SQL `COUNT`) |
| `Model.paginate(page=1, per_page=10)` | dict, see below |
| `Model.select()` | a SQLAlchemy `Select` to build on |

Filters are exact-match `column=value` pairs:

```python
User.filter_all(country="NG", is_active=True)
```

Counts and existence checks run in the database, so they don't load any rows.

### Pagination

```python
User.paginate(page=2, per_page=20)
# {"items": [<User>, ...], "total": 135, "pages": 7, "page": 2, "per_page": 20}
```

Results are ordered by `created_at`, then by primary key, so the same row never appears on two pages. Models without timestamps are ordered by primary key. An out-of-range page returns an empty `items` list rather than an error.

### Anything more complex

For ranges, joins, `OR` and custom ordering, start from `Model.select()` and use SQLAlchemy directly:

```python
stmt = (
    User.select()
    .where(User.created_at >= since, User.email.like("%@example.com"))
    .order_by(User.name)
)
users = db.session.scalars(stmt).all()
page = db.paginate(stmt, page=1, per_page=20)    # Flask-SQLAlchemy pagination object
```

## Typing

Class methods are typed against your model, so editors and type checkers know that `User.get(...)` returns `User | None` and that `User.filter_all(...)` returns `list[User]`.
