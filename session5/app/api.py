from functools import wraps
from flask import Blueprint, current_app, request, jsonify, session

import jwt

from app.extensions import db, limiter
from app.models import Note, User, Role

api_bp = Blueprint("api", __name__, url_prefix="/api")

JWT_ALGO = "HS256"


def _user_id_from_request() -> int | None:
    """Extrae el user_id desde sesion Flask o desde un Bearer JWT."""
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        token = header[7:]
        try:
            payload = jwt.decode(
                token,
                current_app.config["SECRET_KEY"],
                algorithms=[JWT_ALGO],
            )
            return int(payload["sub"])
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    return session.get("user_id")


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        uid = _user_id_from_request()
        if uid is None:
            return jsonify({"error": "authentication required",
                            "login_url": "/login"}), 401
        request.user_id = uid
        return fn(*args, **kwargs)
    return wrapper


def roles_required(*allowed: str):
    """Verifica que el usuario autenticado tenga uno de los roles permitidos.
    Debe aplicarse despues de @login_required (que fija request.user_id)."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = db.session.get(User, request.user_id)
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
    notes = Note.query.filter_by(user_id=request.user_id).all()
    return jsonify([n.to_dict() for n in notes])


@api_bp.route("/notes", methods=["POST"])
@login_required
@limiter.limit("30/minute")
def create_note():
    data = request.get_json() or {}
    if not data.get("title"):
        return jsonify({"error": "title is required"}), 400

    note = Note(
        user_id=request.user_id,
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
        user_id=request.user_id,
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
