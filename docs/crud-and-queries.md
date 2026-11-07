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
- protected fields: `id`, `created_at`, `updated_at` and `deleted_at` by default, plus any you mark

So passing `request.json` directly can't change a primary key or forge a timestamp. Mark more fields protected where you declare them:

```python
from flask_modelkit import protected_column, secret_column

class User(BaseModelMixin, db.Model):
    is_admin = protected_column(db.Boolean, default=False)
    password_hash = secret_column(db.String(255))     # protected and hidden
```

See [Hidden vs protected fields](hidden-and-protected.md) for every way to mark fields and how the two differ.

Protection applies to `update()` and `create_or_abort()`. Plain assignment (`user.is_admin = True`) and `create(...)` still work for trusted code. Don't pass raw request data to `create(**request.json)`: use `create_or_abort(request.json)`.

### Creating from request data: `create_or_abort()`

`create_or_abort()` is `create()` for untrusted input. It validates, drops unsafe keys, and raises a JSON HTTP error instead of crashing:

```python
@app.post("/users")
def register():
    data = request.get_json(silent=True) or {}
    pw = data.get("password")
    user = User.create_or_abort(
        data,
        required=["password"],             # required input that isn't a column
        password_hash=generate_password_hash(pw) if pw else None,
    )
    return jsonify(user.to_dict(json_safe=True)), 201
```

Most endpoints are a single line:

```python
post = Post.create_or_abort(request.get_json(silent=True), author=current_user)
```

What it does, in order:

1. **Rejects a non-object body** with `InvalidBodyError` (400).
2. **Drops keys** that aren't mapped attributes or are in `__protected_fields__`. Pass `fields=["title", "body"]` to accept only those.
3. **Checks the endpoint itself.** If a required column can never be filled, because it is protected or left out of `fields=` and you didn't pass it as a keyword argument, a `TypeError` names the field and the fix. It is raised on every call, even for an empty body, so you find it the first time you try the route.
4. **Checks required fields.** Every `NOT NULL` column without a default is required. Passing a relationship (`author=...`) counts for its foreign-key column. `required=[...]` adds input names that aren't columns. `None` and blank strings count as missing. All missing fields are reported at once with `MissingFieldsError` (400).
5. **Creates and commits.** If a unique value is taken, the session is rolled back and `DuplicateValueError` (409) names the field. Other integrity errors are re-raised so real bugs aren't hidden.

Keyword arguments (`author=`, `password_hash=`) are trusted values: they override `data` and skip protection.

Errors render as JSON without any setup:

```json
{"error": "missing_fields", "message": "Missing required field(s): name, email", "fields": ["name", "email"]}
{"error": "duplicate", "message": "A User with this email already exists.", "fields": ["email"]}
```

They are ordinary Werkzeug `BadRequest`/`Conflict` subclasses, so an `@app.errorhandler(400)` you already have still receives them, with the field names on `e.fields`.

`create_or_abort()` doesn't check value types or formats (for example, that `email` looks like an email). Use a schema library such as marshmallow or pydantic for that, and pass its output in.

### Transactions

`create`, `create_or_abort`, `save`, `update`, `delete`, `soft_delete` and `restore` all commit by default. Pass `commit=False` to group several changes into one transaction:

```python
order = Order.create(user=user, commit=False)
for item in cart:
    OrderLine.create(order=order, product=item, commit=False)
db.session.commit()          # all or nothing
```

`create_or_abort(..., commit=False)` still flushes, so a duplicate value is reported straight away instead of at your final commit. The rollback that comes with a 409 discards every uncommitted change in the session, not only the new row.

If a commit from `create`, `save` or `update` fails, for example on a unique constraint, the session is left in a failed state. Roll it back before using it again:

```python
from sqlalchemy.exc import IntegrityError

try:
    user.update({"email": new_email})
except IntegrityError:
    db.session.rollback()
    abort(409)
```

`create_or_abort()` does this rollback for you.

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
