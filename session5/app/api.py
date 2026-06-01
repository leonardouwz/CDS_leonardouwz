from functools import wraps
from flask import Blueprint, request, jsonify, session

from app.extensions import db, limiter
from app.models import Note, User, Role

api_bp = Blueprint("api", __name__, url_prefix="/api")


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "authentication required",
                            "login_url": "/login"}), 401
        return fn(*args, **kwargs)
    return wrapper


def roles_required(*allowed: str):
    """Verifica que el usuario autenticado tenga uno de los roles permitidos.
    Debe aplicarse despues de @login_required."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = db.session.get(User, session.get("user_id"))
            if user is None:
                return jsonify({"error": "not authenticated"}), 401
            if user.role not in allowed:
                return jsonify({"error": "forbidden", "required_role": list(allowed)}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


@api_bp.route("/notes", methods=["GET"])
@login_required
def list_notes():
    notes = Note.query.filter_by(user_id=session["user_id"]).all()
    return jsonify([n.to_dict() for n in notes])


@api_bp.route("/notes", methods=["POST"])
@login_required
@limiter.limit("30/minute")
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


@api_bp.route("/admin/notes", methods=["GET"])
@login_required
@roles_required(Role.admin)
def admin_list_all_notes():
    notes = Note.query.all()
    return jsonify([
        {**n.to_dict(), "owner_email": n.owner.email}
        for n in notes
    ])
