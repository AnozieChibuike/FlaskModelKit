"""Column-level protection: protected_column, secret_column, info={"protected": True}."""
from flask_modelkit import BaseModel, db, protected_column, secret_column


class Guard(BaseModel):
    __test__ = False
    __protected_fields__ = BaseModel.__protected_fields__ | {"notes"}
    name = db.Column(db.String(50), nullable=False)
    is_admin = protected_column(db.Boolean, default=False, nullable=False)
    role = db.Column(db.String(20), default="user", info={"protected": True, "label": "Role"})
    password_hash = secret_column(db.String(200))
    notes = db.relationship("GuardNote")
    badges = db.relationship("GuardBadge", info={"protected": True})


class GuardNote(BaseModel):
    __test__ = False
    guard_id = db.Column(db.String(126), db.ForeignKey("guard.id"))


class GuardBadge(BaseModel):
    __test__ = False
    guard_id = db.Column(db.String(126), db.ForeignKey("guard.id"))


ATTACK = {
    "is_admin": True,
    "role": "owner",
    "password_hash": "attacker-chosen",
    "notes": [],
    "badges": [],
    "id": "hacked",
}


def test_protected_fields_combines_set_and_column_flags():
    assert Guard.protected_fields() == {
        "id", "created_at", "updated_at", "deleted_at",   # inherited set
        "notes",                                          # class-level union
        "is_admin", "role", "badges",                     # info={"protected": True}
        "password_hash",                                  # secret_column
    }


def test_update_ignores_column_level_protection(app):
    m = Guard.create(name="A", password_hash="real")
    original_id = m.id
    m.update({**ATTACK, "name": "B"})
    assert (m.name, m.is_admin, m.role, m.password_hash, m.id) == ("B", False, "user", "real", original_id)


def test_create_or_abort_drops_protected_input(app):
    m = Guard.create_or_abort({**ATTACK, "name": "A"}, password_hash="real")
    assert (m.is_admin, m.role, m.password_hash) == (False, "user", "real")


def test_trusted_code_can_still_set_protected(app):
    m = Guard.create(name="A", is_admin=True, role="owner")
    m.role = "staff"
    m.save()
    assert (m.is_admin, m.role) == (True, "staff")


def test_secret_column_is_hidden_and_protected(app):
    m = Guard.create(name="A", password_hash="real")
    assert "password_hash" not in m.to_dict()
    m.update({"password_hash": "x"})
    assert m.password_hash == "real"


def test_protected_is_not_hidden(app):
    data = Guard.create(name="A").to_dict()
    assert data["is_admin"] is False and data["role"] == "user"


def test_extra_info_keys_kept():
    assert Guard.__table__.c.role.info == {"protected": True, "label": "Role"}
    assert Guard.__table__.c.password_hash.info == {"hidden": True, "protected": True}
