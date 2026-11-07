from decimal import Decimal

from flask import jsonify

from .models import Account, Author, Book, Chapter


def _tree():
    a = Author.create(name="A")
    b = Book.create(title="B", author=a)
    Chapter.create(title="C", book=b)
    return a


def test_bidirectional_relationship_does_not_recurse(app):
    data = _tree().to_dict(depth=None)
    book = data["books"][0]
    assert book["title"] == "B" and "author" not in book
    assert book["chapters"][0]["title"] == "C"


def test_depth(app):
    a = _tree()
    assert "books" not in a.to_dict(depth=0)
    assert "chapters" not in a.to_dict()["books"][0]          # default depth=1
    assert "chapters" in a.to_dict(depth=2)["books"][0]


def test_exclude(app):
    assert "created_at" not in _tree().to_dict(exclude=["created_at"])


def test_hidden_fields_never_serialised(app):
    acct = Account.create(email="a@x.io", password_hash="secret")
    assert "password_hash" not in acct.to_dict()
    assert "password_hash" not in acct.to_dict(depth=None, json_safe=True)


def test_json_safe(app):
    acct = Account.create(email="a@x.io", balance=Decimal("9.50"))
    data = acct.to_dict(json_safe=True)
    assert data["balance"] == "9.50"
    assert data["status"] == "active"
    assert isinstance(data["created_at"], str)
    with app.test_request_context():
        jsonify(data)
