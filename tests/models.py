"""Models shared by the test suite, all on the package's ``db``."""
import enum
from decimal import Decimal

from flasksqlalchemybasemodel import (
    BaseModel,
    CRUDMixin,
    IntIdMixin,
    SerializerMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDMixin,
    db,
)


class Author(BaseModel):
    __test__ = False
    name = db.Column(db.String(50))
    books = db.relationship("Book", back_populates="author")


class Book(BaseModel):
    __test__ = False
    title = db.Column(db.String(50))
    author_id = db.Column(db.String(126), db.ForeignKey("author.id"))
    author = db.relationship("Author", back_populates="books")
    chapters = db.relationship("Chapter", back_populates="book")


class Chapter(BaseModel):
    __test__ = False
    title = db.Column(db.String(50))
    book_id = db.Column(db.String(126), db.ForeignKey("book.id"))
    book = db.relationship("Book", back_populates="chapters")


class Status(enum.Enum):
    ACTIVE = "active"


class Account(BaseModel):
    __test__ = False
    __hidden_fields__ = frozenset({"password_hash"})
    __protected_fields__ = BaseModel.__protected_fields__ | {"is_admin"}
    email = db.Column(db.String(100))
    password_hash = db.Column(db.String(200))
    is_admin = db.Column(db.Boolean, default=False)
    balance = db.Column(db.Numeric(10, 2), default=Decimal("0"))
    status = db.Column(db.Enum(Status), default=Status.ACTIVE)


class Counter(IntIdMixin, CRUDMixin, SerializerMixin, db.Model):
    __test__ = False
    label = db.Column(db.String(20))


class Post(UUIDMixin, TimestampMixin, SoftDeleteMixin, CRUDMixin, SerializerMixin, db.Model):
    __test__ = False
    title = db.Column(db.String(50))
    comments = db.relationship("Comment", back_populates="post")


class Comment(UUIDMixin, TimestampMixin, SoftDeleteMixin, CRUDMixin, SerializerMixin, db.Model):
    __test__ = False
    body = db.Column(db.String(50))
    post_id = db.Column(db.String(126), db.ForeignKey("post.id"))
    post = db.relationship("Post", back_populates="comments")
