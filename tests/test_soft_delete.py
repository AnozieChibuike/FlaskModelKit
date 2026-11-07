from flasksqlalchemybasemodel import db

from .models import Comment, Post


def test_soft_deleted_rows_hidden_from_helpers(app):
    keep = Post.create(title="keep")
    gone = Post.create(title="gone")
    gone.soft_delete()
    assert gone.is_deleted
    assert [p.title for p in Post.all()] == ["keep"]
    assert Post.count_all() == 1
    assert not Post.exists(title="gone")
    assert Post.filter_one(title="gone") is None
    assert Post.get(gone.id) is None             # from the identity map
    db.session.expunge_all()
    assert Post.get(gone.id) is None             # from the database
    assert Post.paginate()["total"] == 1
    assert Post.get(keep.id) is not None


def test_hidden_from_raw_queries_and_relationships(app):
    post = Post.create(title="p")
    Comment.create(body="ok", post=post)
    Comment.create(body="spam", post=post).soft_delete()
    post_id = post.id
    db.session.expunge_all()
    assert len(db.session.scalars(db.select(Comment)).all()) == 1
    assert Comment.query.count() == 1
    assert [c.body for c in Post.get(post_id).comments] == ["ok"]


def test_include_deleted_and_restore(app):
    p = Post.create(title="p")
    p.soft_delete()
    post_id = p.id
    db.session.expunge_all()
    assert len(db.session.scalars(Post.select(include_deleted=True)).all()) == 1
    found = Post.get(post_id, include_deleted=True)
    found.restore()
    assert Post.get(post_id) is not None and not found.is_deleted


def test_update_cannot_undelete(app):
    p = Post.create(title="p")
    p.soft_delete()
    p.update({"deleted_at": None})
    assert p.is_deleted


def test_delete_is_a_hard_delete(app):
    p = Post.create(title="p")
    p.delete()
    assert db.session.scalars(Post.select(include_deleted=True)).all() == []
