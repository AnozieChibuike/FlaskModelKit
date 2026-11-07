import json

import pytest
from flask import request
from sqlalchemy.exc import IntegrityError

from flask_modelkit import (
    DuplicateValueError,
    InvalidBodyError,
    MissingFieldsError,
    db,
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


def test_other_integrity_errors_are_reraised(app):
    # email is NOT NULL but excluded by `fields`, so the database rejects it.
    with pytest.raises(IntegrityError):
        Customer.create_or_abort({"name": "A", "email": "a@x.io"}, fields=["name"], **PW)


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
