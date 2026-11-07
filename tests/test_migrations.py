"""Schema checks with Alembic (what Flask-Migrate runs under the hood)."""
import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from flask_modelkit import db


def _diff(engine, metadata):
    with engine.connect() as conn:
        return compare_metadata(MigrationContext.configure(conn), metadata)


def test_no_spurious_migrations(app):
    """Defaults are generated in Python, so once the tables exist Alembic
    sees nothing to change: no endless 'alter column' migrations."""
    assert _diff(db.engine, db.metadata) == []


def test_columns_match_published_schema():
    """Guard against accidental schema changes to the shared columns."""
    engine = sa.create_engine("sqlite://")
    legacy = sa.MetaData()
    sa.Table(
        "author", legacy,
        sa.Column("id", sa.String(126), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.Column("name", sa.String(50)),
    )
    legacy.create_all(engine)

    from .models import Author  # noqa: F401

    current = sa.MetaData()
    db.metadata.tables["author"].to_metadata(current)
    assert _diff(engine, current) == []
