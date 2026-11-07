import pytest
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from werkzeug.exceptions import NotFound

from flasksqlalchemybasemodel import BaseModelMixin, CRUDMixin, db

from .models import Account, Author, Counter


def test_update_ignores_protected_and_unknown_fields(app):
    a = Author.create(name="A")
    original = (a.id, a.created_at)
    a.update({"id": "hacked", "created_at": None, "name": "B", "save": "x", "nope": 1})
    assert (a.id, a.created_at) == original
    assert a.name == "B"
    assert callable(a.save) and not hasattr(a, "nope")


def test_protected_fields_can_be_extended(app):
    acct = Account.create(email="a@x.io")
    acct.update({"is_admin": True, "email": "b@x.io"})
    assert acct.is_admin is False and acct.email == "b@x.io"


def test_create_returns_saved_object(app):
    a = Author.create(name="A")
    assert Author.get(a.id) is a


def test_count_uses_sql_count(app, sql):
    for i in range(3):
        Author.create(name=str(i))
    sql.clear()
    assert Author.count_all() == 3
    assert Author.filter_and_count_all(name="1") == 1
    assert all("count(" in s.lower() for s in sql)


def test_exists(app):
    Author.create(name="A")
    assert Author.exists(name="A") and not Author.exists(name="Z")


def test_get_or_404(app):
    with app.test_request_context():
        with pytest.raises(NotFound):
            Author.get_or_404("missing")


def test_get_empty_id(app):
    assert Author.get("") is None and Author.get(None) is None


def test_save_without_commit_can_be_rolled_back(app):
    Author(name="A").save(commit=False)
    db.session.rollback()
    assert Author.count_all() == 0


def test_explicit_id_kept_and_available_before_save(app):
    assert Author(name="A").id
    Author.create(id="custom", name="A")
    assert Author.get("custom").name == "A"


def test_updated_at_changes_on_plain_commit(app):
    a = Author.create(name="A")
    before = a.updated_at
    a.name = "B"
    db.session.commit()
    assert a.updated_at > before


def test_paginate_is_ordered(app):
    for i in range(7):
        Author.create(name=str(i))
    first = Author.paginate(page=1, per_page=5)
    second = Author.paginate(page=2, per_page=5)
    assert (first["total"], first["pages"], len(first["items"]), len(second["items"])) == (7, 2, 5, 2)
    assert [a.name for a in first["items"] + second["items"]] == [str(i) for i in range(7)]


def test_int_id_mixin(app):
    c = Counter.create(label="x")
    assert isinstance(c.id, int)
    assert Counter.get(c.id).label == "x"
    assert Counter.paginate()["total"] == 1


def test_mixin_with_own_db():
    own = SQLAlchemy()

    class Note(BaseModelMixin, own.Model):
        body = own.Column(own.String(50))

    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    own.init_app(app)
    with app.app_context():
        own.create_all()
        Note.create(body="hi")
        assert Note.filter_one(body="hi").body == "hi"
        assert Note.metadata is own.metadata and Note.metadata is not db.metadata


def test_mixin_without_db_model_errors_clearly():
    class Plain(CRUDMixin):
        pass

    with pytest.raises(TypeError, match="db.Model"):
        Plain.count_all()
