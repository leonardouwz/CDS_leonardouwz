from functools import wraps
from flask import Blueprint, request, jsonify, session

from app.extensions import db
from app.models import Note

api_bp = Blueprint("api", __name__, url_prefix="/api")


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "authentication required",
                            "login_url": "/login"}), 401
        return fn(*args, **kwargs)
    return wrapper


@api_bp.route("/notes", methods=["GET"])
@login_required
def list_notes():
    notes = Note.query.filter_by(user_id=session["user_id"]).all()
    return jsonify([n.to_dict() for n in notes])


@api_bp.route("/notes", methods=["POST"])
@login_required
def create_note():
    data = request.get_json() or {}
    if not data.get("title"):
        return jsonify({"error": "title is required"}), 400

    note = Note(
        user_id=session["user_id"],
        title=data["title"],
        body=data.get("body", ""),
    )
    db.session.add(note)
    db.session.commit()
    return jsonify(note.to_dict()), 201


@api_bp.route("/notes/<int:note_id>", methods=["DELETE"])
@login_required
def delete_note(note_id):
    note = Note.query.filter_by(
        id=note_id,
        user_id=session["user_id"],
    ).first_or_404()
    db.session.delete(note)
    db.session.commit()
    return "", 204
