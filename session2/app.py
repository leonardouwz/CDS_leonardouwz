# app.py
from flask import Flask, request, jsonify
from models import db, Task
import config

def create_app():
    app = Flask(__name__)

    # Load configuration
    app.config["SQLALCHEMY_DATABASE_URI"] = config.SQLALCHEMY_DATABASE_URI
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = config.SQLALCHEMY_TRACK_MODIFICATIONS
    app.config["SECRET_KEY"] = config.SECRET_KEY

    # Initialize database with app context
    db.init_app(app)

    # ---------- Health & Root ----------
    @app.route("/")
    def root():
        return jsonify({"message": "Task Manager API (Flask + MySQL + SQLAlchemy)"}), 200

    @app.route("/healthz")
    def health():
        # Lightweight health check
        return jsonify({"status": "ok"}), 200

    # ---------- CRUD: Tasks ----------
    @app.route("/tasks", methods=["GET"])
    def list_tasks():
        """List all tasks."""
        tasks = Task.query.order_by(Task.created_at.desc()).all()
        return jsonify([t.to_dict() for t in tasks]), 200

    @app.route("/tasks/<int:task_id>", methods=["GET"])
    def get_task(task_id):
        """Get a single task by id."""
        task = Task.query.get(task_id)
        if not task:
            return jsonify({"error": "Task not found"}), 404
        return jsonify(task.to_dict()), 200

    @app.route("/tasks", methods=["POST"])
    def create_task():
        """Create a new task."""
        payload = request.get_json(silent=True) or {}
        content = payload.get("content", "").strip()

        if not content:
            return jsonify({"error": "Field 'content' is required and cannot be empty."}), 400

        task = Task(content=content, done=bool(payload.get("done", False)))
        db.session.add(task)
        db.session.commit()
        return jsonify(task.to_dict()), 201

    @app.route("/tasks/<int:task_id>", methods=["PUT"])
    def update_task(task_id):
        """Update content/done for an existing task."""
        task = Task.query.get(task_id)
        if not task:
            return jsonify({"error": "Task not found"}), 404

        payload = request.get_json(silent=True) or {}

        # Only update provided fields
        if "content" in payload:
            new_content = str(payload["content"]).strip()
            if not new_content:
                return jsonify({"error": "Field 'content' cannot be empty."}), 400
            task.content = new_content

        if "done" in payload:
            task.done = bool(payload["done"])

        db.session.commit()
        return jsonify(task.to_dict()), 200

    @app.route("/tasks/<int:task_id>", methods=["DELETE"])
    def delete_task(task_id):
        """Delete a task by id."""
        task = Task.query.get(task_id)
        if not task:
            return jsonify({"error": "Task not found"}), 404
        db.session.delete(task)
        db.session.commit()
        return jsonify({"message": "Task deleted"}), 200

    # ---------- Convenience Filters ----------
    @app.route("/tasks/done", methods=["GET"])
    def list_done():
        tasks = Task.query.filter_by(done=True).order_by(Task.updated_at.desc()).all()
        return jsonify([t.to_dict() for t in tasks]), 200

    @app.route("/tasks/pending", methods=["GET"])
    def list_pending():
        tasks = Task.query.filter_by(done=False).order_by(Task.created_at.desc()).all()
        return jsonify([t.to_dict() for t in tasks]), 200

    return app

# Dev entrypoint
if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
