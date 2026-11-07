import json

import pytest
from flask import request
from sqlalchemy.exc import IntegrityError

from flask_modelkit import (
    BaseModel,
    DuplicateValueError,
    InvalidBodyError,
    MissingFieldsError,
    db,
    protected_column,
)

from .models import Customer, Seat, Ticket

PW = {"password_hash": "hashed"}


def _body(exc):
    return json.loads(exc.get_response().get_data())


def test_missing_fields_listed_in_declaration_order(app):
    with pytest.raises(MissingFieldsError) as e:
        Customer.create_or_abort({"nickname": "x"}, **PW)
    assert e.value.code == 400
    assert e.value.fields == ["name", "email"]
    assert _body(e.value) == {
        "error": "missing_fields",
        "message": "Missing required field(s): name, email",
        "fields": ["name", "email"],
    }
    assert Customer.count_all() == 0


def test_blank_and_none_count_as_missing(app):
    with pytest.raises(MissingFieldsError) as e:
        Customer.create_or_abort({"name": "   ", "email": None}, **PW)
    assert e.value.fields == ["name", "email"]


def test_none_body_reports_everything_missing(app):
    with pytest.raises(MissingFieldsError) as e:
        Customer.create_or_abort(None, **PW)
    assert e.value.fields == ["name", "email"]


def test_non_object_body(app):
    with pytest.raises(InvalidBodyError) as e:
        Customer.create_or_abort(["name"])
    assert e.value.code == 400 and _body(e.value)["error"] == "invalid_body"


def test_unknown_and_protected_keys_dropped(app):
    c = Customer.create_or_abort(
        {"name": "A", "email": "a@x.io", "id": "forged", "created_at": "1970",
         "is_vip": True, "password_hash": "client-set", "nonsense": 1},
        **PW,
    )
    assert c.id != "forged" and c.is_vip is False
    assert c.password_hash == "hashed"          # trusted values win over data
    assert db.session.get(Customer, c.id) is c


def test_fields_allowlist(app):
    c = Customer.create_or_abort(
        {"name": "A", "email": "a@x.io", "nickname": "dropped"},
        fields=["name", "email"], **PW,
    )
    assert c.nickname is None


def test_required_extra_input_and_derived_value(app):
    with pytest.raises(MissingFieldsError) as e:
        Customer.create_or_abort({"name": "A"}, required=["password"], **PW)
    assert e.value.fields == ["email", "password"]

    data = {"name": "A", "email": "a@x.io", "password": "pw"}
    c = Customer.create_or_abort(data, required=["password"],
                                 password_hash=data["password"][::-1])
    assert c.password_hash == "wp"


def test_relationship_satisfies_foreign_key(app):
    c = Customer.create_or_abort({"name": "A", "email": "a@x.io"}, **PW)
    with pytest.raises(MissingFieldsError) as e:
        Ticket.create_or_abort({"title": "T"})
    assert e.value.fields == ["customer_id"]
    t = Ticket.create_or_abort({"title": "T"}, customer=c)
    assert t.customer_id == c.id


def test_duplicate_unique_field(app):
    Customer.create_or_abort({"name": "A", "email": "a@x.io"}, **PW)
    with pytest.raises(DuplicateValueError) as e:
        Customer.create_or_abort({"name": "B", "email": "a@x.io"}, **PW)
    assert e.value.code == 409
    assert _body(e.value) == {
        "error": "duplicate",
        "message": "A Customer with this email already exists.",
        "fields": ["email"],
    }
    # The session was rolled back and is usable again.
    Customer.create_or_abort({"name": "B", "email": "b@x.io"}, **PW)
    assert Customer.count_all() == 2


def test_duplicate_detected_against_soft_deleted_row(app):
    c = Customer.create_or_abort({"name": "A", "email": "a@x.io"}, **PW)
    c.soft_delete()
    with pytest.raises(DuplicateValueError) as e:
        Customer.create_or_abort({"name": "B", "email": "a@x.io"}, **PW)
    assert e.value.fields == ["email"]


def test_duplicate_composite_unique(app):
    Seat.create_or_abort({"row": "A", "number": 1})
    Seat.create_or_abort({"row": "A", "number": 2})
    with pytest.raises(DuplicateValueError) as e:
        Seat.create_or_abort({"row": "A", "number": 1})
    assert e.value.fields == ["row", "number"]


def test_commit_false_still_detects_duplicates(app):
    Customer.create_or_abort({"name": "A", "email": "a@x.io"}, **PW)
    c = Customer.create_or_abort({"name": "B", "email": "b@x.io"}, commit=False, **PW)
    assert c in db.session
    with pytest.raises(DuplicateValueError):
        Customer.create_or_abort({"name": "C", "email": "a@x.io"}, commit=False, **PW)


class Gauge(BaseModel):
    __test__ = False
    level = db.Column(db.Integer, db.CheckConstraint("level >= 0", name="level_non_negative"), nullable=False)


class Badge(BaseModel):
    __test__ = False
    label = db.Column(db.String(20), nullable=False)
    code = protected_column(db.String(20), nullable=False)
    owner_id = protected_column(db.String(126), db.ForeignKey("customer.id"), nullable=False)
    owner = db.relationship("Customer", info={"protected": True})


def test_other_integrity_errors_are_reraised(app):
    # A CHECK constraint violation is a real database error, not a duplicate.
    with pytest.raises(IntegrityError):
        Gauge.create_or_abort({"level": -1})
    assert Gauge.count_all() == 0          # session was rolled back and is usable


def _customer():
    return Customer.create(name="C", email="c@x.io", **PW)


def test_protected_required_field_not_passed_is_a_clear_type_error(app):
    owner = _customer()
    with pytest.raises(TypeError) as e:
        Badge.create_or_abort({"label": "x", "code": "ABC"}, owner=owner)
    msg = str(e.value)
    assert "Badge.create_or_abort()" in msg and "'code' is protected" in msg
    assert "Badge.create_or_abort(data, code=...)" in msg
    assert "owner_id" not in msg               # satisfied by the owner= relationship
    assert Badge.count_all() == 0


def test_type_error_raised_even_when_request_is_incomplete(app):
    # The bug is in the endpoint, so it surfaces on every call, before any 400.
    with pytest.raises(TypeError, match="code, owner_id"):
        Badge.create_or_abort({})


def test_protected_required_field_passed_as_keyword_works(app):
    owner = _customer()
    badge = Badge.create_or_abort({"label": "x", "code": "HACK"}, code="ABC", owner=owner)
    assert (badge.code, badge.owner_id) == ("ABC", owner.id)


def test_foreign_key_passed_directly_counts(app):
    owner = _customer()
    badge = Badge.create_or_abort({"label": "x"}, code="ABC", owner_id=owner.id)
    assert badge.owner is owner


def test_field_left_out_of_fields_allowlist_is_a_clear_type_error(app):
    with pytest.raises(TypeError, match=r"'email' is not in fields=\['name'\]"):
        Customer.create_or_abort({"name": "A", "email": "a@x.io"}, fields=["name"], **PW)


def test_blank_trusted_value_still_reports_missing_input(app):
    # Docs pattern: password_hash=None when the password is missing → 400, not TypeError.
    with pytest.raises(MissingFieldsError) as e:
        Customer.create_or_abort({"name": "A", "email": "a@x.io"}, required=["password"], password_hash=None)
    assert e.value.fields == ["password"]


def test_through_a_flask_route(app):
    @app.post("/customers")
    def create_customer():
        c = Customer.create_or_abort(request.get_json(silent=True), **PW)
        return c.to_dict(json_safe=True), 201

    client = app.test_client()
    r = client.post("/customers", json={"name": "A"})
    assert r.status_code == 400 and r.is_json
    assert r.get_json()["fields"] == ["email"]

    r = client.post("/customers", json={"name": "A", "email": "a@x.io"})
    assert r.status_code == 201 and "password_hash" not in r.get_json()

    r = client.post("/customers", json={"name": "B", "email": "a@x.io"})
    assert r.status_code == 409 and r.get_json()["fields"] == ["email"]
