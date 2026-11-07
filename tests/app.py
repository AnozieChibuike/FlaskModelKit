from flask import Flask

from flask_modelkit import db


class TestConfig:
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False


def create_app():
    app = Flask(__name__)
    app.config.from_object(TestConfig)
    db.init_app(app)
    return app
