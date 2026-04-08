from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # permite peticiones desde el HTML abierto en el navegador

# ─────────────────────────────────────────────
#  DATOS EN MEMORIA
# ─────────────────────────────────────────────
tasks = []
users = []
task_counter = 1
user_counter = 1

@app.route("/")
def frontend():
    return send_file('index.html', as_attachment=False)

# ─────────────────────────────────────────────
#  TASKS ENDPOINTS
# ─────────────────────────────────────────────

# GET /tasks  → listar todas las tareas
@app.route("/tasks", methods=["GET"])
def get_tasks():
    return jsonify({"tasks": tasks})


# GET /tasks/<id>  → obtener una tarea por ID
@app.route("/tasks/<int:task_id>", methods=["GET"])
def get_task(task_id):
    task = next((t for t in tasks if t["id"] == task_id), None)
    if task is None:
        return jsonify({"error": "Task not found"}), 404
    return jsonify({"task": task})


# POST /tasks  → crear tarea
@app.route("/tasks", methods=["POST"])
def add_task():
    global task_counter
    data = request.json

    content = data.get("content", "").strip()
    if not content:
        return jsonify({"error": "Content cannot be empty"}), 400

    task = {
        "id": task_counter,
        "content": content,
        "done": False,
    }
    tasks.append(task)
    task_counter += 1
    return jsonify({"message": "Task added!", "task": task}), 201


# PUT /tasks/<id>  → actualizar contenido y/o estado
@app.route("/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id):
    task = next((t for t in tasks if t["id"] == task_id), None)
    if task is None:
        return jsonify({"error": "Task not found"}), 404

    data = request.json
    if "content" in data:
        content = data["content"].strip()
        if not content:
            return jsonify({"error": "Content cannot be empty"}), 400
        task["content"] = content
    if "done" in data:
        task["done"] = bool(data["done"])

    return jsonify({"message": "Task updated!", "task": task})


# DELETE /tasks/<id>  → eliminar tarea
@app.route("/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id):
    task = next((t for t in tasks if t["id"] == task_id), None)
    if task is None:
        return jsonify({"error": "Task not found"}), 404
    tasks.remove(task)
    return jsonify({"message": "Task deleted!", "task": task})


# ─────────────────────────────────────────────
#  USERS ENDPOINTS
# ─────────────────────────────────────────────

def validate_user(data):
    """Valida los campos requeridos de un usuario."""
    name = data.get("name", "").strip()
    lastname = data.get("lastname", "").strip()
    address = data.get("address", {})

    if not name:
        return None, "Name is required"
    if not lastname:
        return None, "Lastname is required"
    if not isinstance(address, dict):
        return None, "Address must be an object"

    city = address.get("city", "").strip()
    country = address.get("country", "").strip()
    code = address.get("code", "").strip()

    if not city or not country or not code:
        return None, "Address must include city, country, and code"

    return {
        "name": name,
        "lastname": lastname,
        "address": {"city": city, "country": country, "code": code},
    }, None


# GET /users  → listar todos
@app.route("/users", methods=["GET"])
def get_users():
    return jsonify({"users": users})


# GET /users/<id>  → obtener uno
@app.route("/users/<int:user_id>", methods=["GET"])
def get_user(user_id):
    user = next((u for u in users if u["id"] == user_id), None)
    if user is None:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"user": user})


# POST /users  → crear usuario
@app.route("/users", methods=["POST"])
def add_user():
    global user_counter
    data = request.json or {}
    fields, error = validate_user(data)
    if error:
        return jsonify({"error": error}), 400

    user = {"id": user_counter, **fields}
    users.append(user)
    user_counter += 1
    return jsonify({"message": "User created!", "user": user}), 201


# PUT /users/<id>  → actualizar usuario
@app.route("/users/<int:user_id>", methods=["PUT"])
def update_user(user_id):
    user = next((u for u in users if u["id"] == user_id), None)
    if user is None:
        return jsonify({"error": "User not found"}), 404

    data = request.json or {}
    fields, error = validate_user(data)
    if error:
        return jsonify({"error": error}), 400

    user.update(fields)
    return jsonify({"message": "User updated!", "user": user})


# DELETE /users/<id>  → eliminar usuario
@app.route("/users/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):
    user = next((u for u in users if u["id"] == user_id), None)
    if user is None:
        return jsonify({"error": "User not found"}), 404
    users.remove(user)
    return jsonify({"message": "User deleted!", "user": user})


# ─────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True)
