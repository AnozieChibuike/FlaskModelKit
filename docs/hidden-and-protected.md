# Hidden vs protected fields

These are two separate controls over what crosses your API boundary:

| | **Hidden** | **Protected** |
|---|---|---|
| Stops data going… | **out**, to the client | **in**, from the client |
| Applies to | `to_dict()` | `update()`, `create_or_abort()` |
| Mark a column | `hidden_column(...)` or `info={"hidden": True}` | `protected_column(...)` or `info={"protected": True}` |
| Mark by name | `__hidden_fields__` | `__protected_fields__` |
| Defaults | nothing | `id`, `created_at`, `updated_at`, `deleted_at` |
| Typical fields | write-only input (a webhook secret the user pastes in), large relationships | `is_admin`, `role`, `owner_id`, `balance` |

A field can be either, both or neither. For fields that need **both**, use `secret_column(...)`:

| Field | Hidden | Protected | Declare with |
|---|:-:|:-:|---|
| `name`, `bio` | | | `db.Column(...)` |
| `is_admin`, `role` | | ✓ | `protected_column(...)` |
| A webhook secret the user pastes in (write-only) | ✓ | | `hidden_column(...)` |
| `password_hash`, `api_key`, `reset_token`, `internal_notes` | ✓ | ✓ | `secret_column(...)` |

```python
from flask_modelkit import BaseModelMixin, hidden_column, protected_column, secret_column

class User(BaseModelMixin, db.Model):
    name = db.Column(db.String(80), nullable=False)
    is_admin = protected_column(db.Boolean, default=False, nullable=False)
    webhook_secret = hidden_column(db.String(64))   # write-only: accepted, never sent back
    password_hash = secret_column(db.String(255), nullable=False)
```

## Hidden alone does not protect a secret

This is the mistake the table above exists to prevent:

```python
password_hash = hidden_column(db.String(255))     # hidden, but NOT protected

user.update(request.json)   # body: {"password_hash": "<attacker's hash>"}
```

The hash never appears in responses, but the client just replaced it. Anyone who sets the hash can then log in with a password of their choosing. Secrets must be `secret_column`.

The reverse applies too: `protected_column` keeps `is_admin` from being *set*, but it still appears in `to_dict()`. Usually that's fine and even wanted, since the UI may need to show it.

## The three ways to mark a field

All three are combined, so you can mix them. `Model.protected_fields()` returns the final set.

**1. Shorthand helpers.** These are the most readable option for columns you declare:

```python
is_admin = protected_column(db.Boolean, default=False)
```

`hidden_column`, `protected_column` and `secret_column` take exactly the same arguments as `db.Column`.

**2. `info=` flags.** Use these for relationships, or when you'd rather keep `db.Column`:

```python
role = db.Column(db.String(20), default="user", info={"protected": True})
posts = db.relationship("Post", back_populates="author", info={"protected": True})
api_key = db.Column(db.String(64), info={"hidden": True, "protected": True})
```

`info` is SQLAlchemy's own metadata dictionary, so other keys you put there are kept.

**3. Class-level sets.** Use these for fields you don't declare yourself, such as columns inherited from a mixin or a base class:

```python
class User(BaseModelMixin, db.Model):
    __protected_fields__ = BaseModelMixin.__protected_fields__ | {"email"}
    __hidden_fields__ = frozenset({"updated_at"})
```

### About the `|`

`|` is Python's set **union** operator. `a | b` is a new set containing everything in either set:

```python
{"id", "created_at"} | {"email"}     # {"id", "created_at", "email"}
```

When you replace `__protected_fields__`, start from the inherited set, so the defaults stay protected:

```python
__protected_fields__ = BaseModelMixin.__protected_fields__ | {"email"}   # id, timestamps, email
__protected_fields__ = frozenset({"email"})                             # only email: id is now writable!
```

The column-level helpers don't have this pitfall, which is one reason to prefer them.

## Protected only applies to input

Protection filters *client data* passed to `update()` and `create_or_abort()`. Your own code can always set protected fields:

```python
user.is_admin = True                                  # plain assignment
User.create(name="Ada", is_admin=True)                # create() is for trusted values
User.create_or_abort(data, password_hash=hash_pw(pw)) # keyword arguments are trusted
```

This also means a protected, `NOT NULL` column without a default must always be passed as a keyword argument to `create_or_abort()`. Client input can never fill it, and if you forget, `create_or_abort()` raises a `TypeError` naming the field:

```python
data = request.get_json(silent=True) or {}
user = User.create_or_abort(
    data,
    required=["password"],
    password_hash=generate_password_hash(data["password"]) if data.get("password") else None,
)
```
