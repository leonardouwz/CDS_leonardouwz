# app.py
from flask import Flask, request, jsonify
from models import db, Task, User
from datetime import datetime
import config


def create_app():
    app = Flask(__name__)

    app.config["SQLALCHEMY_DATABASE_URI"] = config.SQLALCHEMY_DATABASE_URI
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = config.SQLALCHEMY_TRACK_MODIFICATIONS
    app.config["SECRET_KEY"] = config.SECRET_KEY

    db.init_app(app)

    # ──────────────────────────────────────────────
    # Health
    # ──────────────────────────────────────────────

    @app.route("/")
    def root():
        return jsonify({"message": "Task Manager API – Flask + MySQL/PostgreSQL + SQLAlchemy"}), 200

    @app.route("/healthz")
    def health():
        return jsonify({"status": "ok"}), 200

    # ──────────────────────────────────────────────
    # TASKS – CRUD
    # ──────────────────────────────────────────────

    @app.route("/tasks", methods=["GET"])
    def list_tasks():
        """
        List active (non-deleted) tasks.

        Stretch goal 1 – Pagination:   ?page=1&limit=20
        Stretch goal 2 – Search:       ?query=<text>
        Filter by status:              ?done=true|false
        Filter by user:                ?user_id=<id>
        """
        # --- base query: only non-deleted tasks ---
        query = Task.query.filter(Task.deleted_at.is_(None))

        # Stretch goal 2: search by content (case-insensitive)
        search = request.args.get("query", "").strip()
        if search:
            query = query.filter(Task.content.ilike(f"%{search}%"))

        # Filter by done status
        done_param = request.args.get("done")
        if done_param is not None:
            query = query.filter(Task.done == (done_param.lower() == "true"))

        # Filter by user
        user_id = request.args.get("user_id")
        if user_id:
            query = query.filter(Task.user_id == int(user_id))

        query = query.order_by(Task.created_at.desc())

        # Stretch goal 1: pagination
        page = max(int(request.args.get("page", 1)), 1)
        limit = min(int(request.args.get("limit", 20)), 100)  # cap at 100

        total = query.count()
        tasks = query.offset((page - 1) * limit).limit(limit).all()

        return jsonify({
            "data": [t.to_dict() for t in tasks],
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit,
            },
        }), 200

    @app.route("/tasks/<int:task_id>", methods=["GET"])
    def get_task(task_id):
        task = Task.query.filter_by(id=task_id).filter(Task.deleted_at.is_(None)).first()
        if not task:
            return jsonify({"error": "Task not found"}), 404
        return jsonify(task.to_dict()), 200

    @app.route("/tasks", methods=["POST"])
    def create_task():
        payload = request.get_json(silent=True) or {}
        content = payload.get("content", "").strip()

        if not content:
            return jsonify({"error": "Field 'content' is required and cannot be empty."}), 400

        # Validate user_id if provided
        user_id = payload.get("user_id")
        if user_id is not None:
            user = User.query.filter_by(id=user_id).filter(User.deleted_at.is_(None)).first()
            if not user:
                return jsonify({"error": f"User {user_id} not found."}), 404

        task = Task(
            content=content,
            done=bool(payload.get("done", False)),
            user_id=user_id,
        )
        db.session.add(task)
        db.session.commit()
        return jsonify(task.to_dict()), 201

    @app.route("/tasks/<int:task_id>", methods=["PUT"])
    def update_task(task_id):
        task = Task.query.filter_by(id=task_id).filter(Task.deleted_at.is_(None)).first()
        if not task:
            return jsonify({"error": "Task not found"}), 404

        payload = request.get_json(silent=True) or {}

        if "content" in payload:
            new_content = str(payload["content"]).strip()
            if not new_content:
                return jsonify({"error": "Field 'content' cannot be empty."}), 400
            task.content = new_content

        if "done" in payload:
            task.done = bool(payload["done"])

        if "user_id" in payload:
            uid = payload["user_id"]
            if uid is not None:
                user = User.query.filter_by(id=uid).filter(User.deleted_at.is_(None)).first()
                if not user:
                    return jsonify({"error": f"User {uid} not found."}), 404
            task.user_id = uid

        db.session.commit()
        return jsonify(task.to_dict()), 200

    @app.route("/tasks/<int:task_id>", methods=["DELETE"])
    def delete_task(task_id):
        """
        Stretch goal 3 – Soft delete.
        Pass ?hard=true to permanently remove the record.
        """
        task = Task.query.filter_by(id=task_id).filter(Task.deleted_at.is_(None)).first()
        if not task:
            return jsonify({"error": "Task not found"}), 404

        if request.args.get("hard", "").lower() == "true":
            db.session.delete(task)
            db.session.commit()
            return jsonify({"message": "Task permanently deleted"}), 200

        # Soft delete: stamp deleted_at
        task.deleted_at = datetime.utcnow()
        db.session.commit()
        return jsonify({"message": "Task soft-deleted", "task": task.to_dict()}), 200

    @app.route("/tasks/<int:task_id>/restore", methods=["POST"])
    def restore_task(task_id):
        """Restore a soft-deleted task."""
        task = Task.query.filter_by(id=task_id).filter(Task.deleted_at.isnot(None)).first()
        if not task:
            return jsonify({"error": "Deleted task not found"}), 404
        task.deleted_at = None
        db.session.commit()
        return jsonify(task.to_dict()), 200

    # Convenience filters
    @app.route("/tasks/done", methods=["GET"])
    def list_done():
        tasks = (Task.query
                 .filter_by(done=True)
                 .filter(Task.deleted_at.is_(None))
                 .order_by(Task.updated_at.desc())
                 .all())
        return jsonify([t.to_dict() for t in tasks]), 200

    @app.route("/tasks/pending", methods=["GET"])
    def list_pending():
        tasks = (Task.query
                 .filter_by(done=False)
                 .filter(Task.deleted_at.is_(None))
                 .order_by(Task.created_at.desc())
                 .all())
        return jsonify([t.to_dict() for t in tasks]), 200

    @app.route("/tasks/deleted", methods=["GET"])
    def list_deleted():
        """List all soft-deleted tasks."""
        tasks = Task.query.filter(Task.deleted_at.isnot(None)).order_by(Task.deleted_at.desc()).all()
        return jsonify([t.to_dict() for t in tasks]), 200

    # ──────────────────────────────────────────────
    # USERS – CRUD  (Stretch goal 4)
    # ──────────────────────────────────────────────

    @app.route("/users", methods=["GET"])
    def list_users():
        """List active users. Supports ?page, ?limit, ?query."""
        query = User.query.filter(User.deleted_at.is_(None))

        search = request.args.get("query", "").strip()
        if search:
            query = query.filter(
                (User.username.ilike(f"%{search}%")) | (User.email.ilike(f"%{search}%"))
            )

        query = query.order_by(User.created_at.desc())

        page = max(int(request.args.get("page", 1)), 1)
        limit = min(int(request.args.get("limit", 20)), 100)
        total = query.count()
        users = query.offset((page - 1) * limit).limit(limit).all()

        return jsonify({
            "data": [u.to_dict() for u in users],
            "pagination": {"page": page, "limit": limit, "total": total,
                           "pages": (total + limit - 1) // limit},
        }), 200

    @app.route("/users/<int:user_id>", methods=["GET"])
    def get_user(user_id):
        user = User.query.filter_by(id=user_id).filter(User.deleted_at.is_(None)).first()
        if not user:
            return jsonify({"error": "User not found"}), 404
        include_tasks = request.args.get("include_tasks", "false").lower() == "true"
        return jsonify(user.to_dict(include_tasks=include_tasks)), 200

    @app.route("/users", methods=["POST"])
    def create_user():
        payload = request.get_json(silent=True) or {}
        username = payload.get("username", "").strip()
        email = payload.get("email", "").strip()

        if not username or not email:
            return jsonify({"error": "Fields 'username' and 'email' are required."}), 400

        if User.query.filter_by(username=username).first():
            return jsonify({"error": "Username already taken."}), 409
        if User.query.filter_by(email=email).first():
            return jsonify({"error": "Email already registered."}), 409

        user = User(username=username, email=email)
        db.session.add(user)
        db.session.commit()
        return jsonify(user.to_dict()), 201

    @app.route("/users/<int:user_id>", methods=["PUT"])
    def update_user(user_id):
        user = User.query.filter_by(id=user_id).filter(User.deleted_at.is_(None)).first()
        if not user:
            return jsonify({"error": "User not found"}), 404

        payload = request.get_json(silent=True) or {}

        if "username" in payload:
            new_name = str(payload["username"]).strip()
            if not new_name:
                return jsonify({"error": "Field 'username' cannot be empty."}), 400
            existing = User.query.filter_by(username=new_name).first()
            if existing and existing.id != user_id:
                return jsonify({"error": "Username already taken."}), 409
            user.username = new_name

        if "email" in payload:
            new_email = str(payload["email"]).strip()
            if not new_email:
                return jsonify({"error": "Field 'email' cannot be empty."}), 400
            existing = User.query.filter_by(email=new_email).first()
            if existing and existing.id != user_id:
                return jsonify({"error": "Email already registered."}), 409
            user.email = new_email

        db.session.commit()
        return jsonify(user.to_dict()), 200

    @app.route("/users/<int:user_id>", methods=["DELETE"])
    def delete_user(user_id):
        """
        Soft-deletes the user and optionally their tasks.
        Pass ?cascade=true to soft-delete all user tasks too.
        Pass ?hard=true for permanent deletion.
        """
        user = User.query.filter_by(id=user_id).filter(User.deleted_at.is_(None)).first()
        if not user:
            return jsonify({"error": "User not found"}), 404

        hard = request.args.get("hard", "false").lower() == "true"
        cascade = request.args.get("cascade", "false").lower() == "true"

        if hard:
            db.session.delete(user)
            db.session.commit()
            return jsonify({"message": "User permanently deleted"}), 200

        now = datetime.utcnow()
        user.deleted_at = now

        if cascade:
            Task.query.filter_by(user_id=user_id).filter(Task.deleted_at.is_(None)).update(
                {"deleted_at": now}
            )

        db.session.commit()
        return jsonify({"message": "User soft-deleted", "user": user.to_dict()}), 200

    @app.route("/users/<int:user_id>/restore", methods=["POST"])
    def restore_user(user_id):
        user = User.query.filter_by(id=user_id).filter(User.deleted_at.isnot(None)).first()
        if not user:
            return jsonify({"error": "Deleted user not found"}), 404
        user.deleted_at = None
        db.session.commit()
        return jsonify(user.to_dict()), 200

    @app.route("/users/<int:user_id>/tasks", methods=["GET"])
    def user_tasks(user_id):
        """List active tasks for a specific user. Supports pagination & search."""
        user = User.query.filter_by(id=user_id).filter(User.deleted_at.is_(None)).first()
        if not user:
            return jsonify({"error": "User not found"}), 404

        q = Task.query.filter_by(user_id=user_id).filter(Task.deleted_at.is_(None))

        search = request.args.get("query", "").strip()
        if search:
            q = q.filter(Task.content.ilike(f"%{search}%"))

        page = max(int(request.args.get("page", 1)), 1)
        limit = min(int(request.args.get("limit", 20)), 100)
        total = q.count()
        tasks = q.order_by(Task.created_at.desc()).offset((page - 1) * limit).limit(limit).all()

        return jsonify({
            "user": user.to_dict(),
            "data": [t.to_dict() for t in tasks],
            "pagination": {"page": page, "limit": limit, "total": total,
                           "pages": (total + limit - 1) // limit},
        }), 200

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)