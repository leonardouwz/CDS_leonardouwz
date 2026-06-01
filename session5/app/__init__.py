import os
from dotenv import load_dotenv
from flask import Flask

from app.extensions import db
from app.auth import auth_bp
from app.api import api_bp

load_dotenv()


def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ["FLASK_SECRET_KEY"]
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DATABASE_URI"]
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp)

    with app.app_context():
        db.create_all()

    @app.route("/")
    def index():
        return (
            '<h2>Notes API</h2>'
            '<a href="/login">Login with Google</a> | '
            '<a href="/api/notes">My notes</a> | '
            '<a href="/me">My profile</a> | '
            '<a href="/logout">Logout</a>'
        )

    return app
