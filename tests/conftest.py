import pytest

from flask_modelkit import db

from .app import create_app


@pytest.fixture
def app():
    app = create_app()
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def sql(app):
    """List that collects every SQL statement executed during the test."""
    from sqlalchemy import event

    statements: list[str] = []
    listener = lambda *args: statements.append(args[2])  # noqa: E731
    event.listen(db.engine, "before_cursor_execute", listener)
    yield statements
    event.remove(db.engine, "before_cursor_execute", listener)
