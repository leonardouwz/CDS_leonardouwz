# Session 2 – Stretch Goals (Homework)

> Extensiones sobre el proyecto **Flask + MySQL + SQLAlchemy** del laboratorio.  
> Cada goal modifica o agrega código al proyecto base; los archivos finales listos para copiar están incluidos.

---

## Índice

1. [Paginación en `GET /tasks`](#1-paginación)
2. [Búsqueda por contenido](#2-búsqueda)
3. [Soft Delete](#3-soft-delete)
4. [CRUD de Users con relación a Tasks](#4-users)
5. [Migración a PostgreSQL](#5-postgresql)

---

## 1 · Paginación

**Objetivo:** `GET /tasks?page=1&limit=20` devuelve una "página" de resultados en lugar de todos los registros.

### ¿Por qué paginar?

Sin paginación, con miles de tareas en BD, la API devuelve todo a la vez → memoria alta, respuesta lenta, cliente saturado.

### Cambios en `app.py`

```python
# Dentro de list_tasks()

# Parámetros desde la query string; valores por defecto seguros
page  = max(int(request.args.get("page",  1)),   1)   # mínimo página 1
limit = min(int(request.args.get("limit", 20)), 100)  # máximo 100 por página

total = query.count()   # total de registros que coinciden

tasks = (query
         .offset((page - 1) * limit)   # cuántos saltar
         .limit(limit)                 # cuántos traer
         .all())

return jsonify({
    "data": [t.to_dict() for t in tasks],
    "pagination": {
        "page":  page,
        "limit": limit,
        "total": total,
        "pages": (total + limit - 1) // limit,   # total de páginas (ceil)
    },
}), 200
```

**SQL equivalente generado por SQLAlchemy:**
```sql
SELECT * FROM tasks
WHERE deleted_at IS NULL
ORDER BY created_at DESC
LIMIT 20 OFFSET 0;      -- page 1
-- OFFSET 20            -- page 2
-- OFFSET 40            -- page 3 …
```

### Prueba con cURL

```bash
# Página 1, 5 tareas por página
curl "http://127.0.0.1:5000/tasks?page=1&limit=5"

# Página 2
curl "http://127.0.0.1:5000/tasks?page=2&limit=5"
```

**Respuesta:**
```json
{
  "data": [ { "id": 3, "content": "...", ... } ],
  "pagination": { "page": 1, "limit": 5, "total": 12, "pages": 3 }
}
```

---

## 2 · Búsqueda por contenido

**Objetivo:** `GET /tasks?query=flask` filtra tareas cuyo `content` contenga la palabra buscada.

### Cambios en `app.py`

```python
search = request.args.get("query", "").strip()
if search:
    query = query.filter(Task.content.ilike(f"%{search}%"))
```

- `ilike` → `LIKE` insensible a mayúsculas/minúsculas (funciona igual en MySQL y PostgreSQL).
- Los `%` son comodines SQL: `%flask%` coincide con cualquier string que contenga "flask".

**SQL generado:**
```sql
SELECT * FROM tasks
WHERE deleted_at IS NULL
  AND content LIKE '%flask%'   -- case-insensitive
ORDER BY created_at DESC;
```

### Combinación con paginación

Los filtros se apilan **antes** de paginar, por lo que `total` siempre refleja los resultados filtrados:

```bash
curl "http://127.0.0.1:5000/tasks?query=mysql&page=1&limit=10"
```

### Búsqueda en Users

El mismo patrón aplica en `GET /users?query=<text>`, buscando en `username` OR `email`:

```python
query = query.filter(
    (User.username.ilike(f"%{search}%")) | (User.email.ilike(f"%{search}%"))
)
```

---

## 3 · Soft Delete

**Objetivo:** en lugar de borrar el registro de la BD, se marca con `deleted_at = NOW()`. Así los datos son recuperables y queda auditoría.

### Cambio en `models.py`

```python
class Task(db.Model):
    # … columnas existentes …
    deleted_at = db.Column(db.DateTime, nullable=True)   # NULL = activo
```

| `deleted_at` | Significado |
|---|---|
| `NULL` | Tarea activa |
| `2025-01-15T10:30:00` | Tarea eliminada en esa fecha |

### Cambio en todas las consultas

Cada query debe excluir los soft-deleted:

```python
# ❌ Antes (trae todo, incluso borrados)
Task.query.all()

# ✅ Ahora (solo activos)
Task.query.filter(Task.deleted_at.is_(None)).all()
```

### Endpoint DELETE actualizado

```python
@app.route("/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id):
    task = Task.query.filter_by(id=task_id).filter(Task.deleted_at.is_(None)).first()
    if not task:
        return jsonify({"error": "Task not found"}), 404

    if request.args.get("hard", "").lower() == "true":
        # Borrado permanente (hard delete)
        db.session.delete(task)
        db.session.commit()
        return jsonify({"message": "Task permanently deleted"}), 200

    # Soft delete: solo stampamos la fecha
    task.deleted_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"message": "Task soft-deleted", "task": task.to_dict()}), 200
```

### Nuevo endpoint: restaurar

```python
@app.route("/tasks/<int:task_id>/restore", methods=["POST"])
def restore_task(task_id):
    task = Task.query.filter_by(id=task_id).filter(Task.deleted_at.isnot(None)).first()
    if not task:
        return jsonify({"error": "Deleted task not found"}), 404
    task.deleted_at = None
    db.session.commit()
    return jsonify(task.to_dict()), 200
```

### Prueba con cURL

```bash
# Soft delete
curl -X DELETE http://127.0.0.1:5000/tasks/1

# Ver tareas eliminadas
curl http://127.0.0.1:5000/tasks/deleted

# Restaurar
curl -X POST http://127.0.0.1:5000/tasks/1/restore

# Hard delete (permanente)
curl -X DELETE "http://127.0.0.1:5000/tasks/1?hard=true"
```

---

## 4 · CRUD de Users (con relación a Tasks)

**Objetivo:** agregar un modelo `User`; cada `Task` puede pertenecer a un `User` (relación uno-a-muchos).

### Diagrama de relación

```
users                tasks
──────               ──────────────────
id  ◄────────────── user_id (FK, nullable)
username             content
email                done
created_at           created_at
deleted_at           deleted_at
```

Un usuario puede tener muchas tareas. Una tarea puede no tener usuario (`user_id = NULL`).

### Modelo `User` en `models.py`

```python
class User(db.Model):
    __tablename__ = "users"

    id         = db.Column(db.Integer, primary_key=True)
    username   = db.Column(db.String(80),  unique=True, nullable=False)
    email      = db.Column(db.String(120), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)   # soft delete

    # Relación ORM: user.tasks → lista de Task
    tasks = db.relationship("Task", backref="owner", lazy=True)
```

### FK en `Task`

```python
class Task(db.Model):
    # … columnas existentes …
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
```

### Endpoints de Users

| Método | URL | Descripción |
|---|---|---|
| GET | `/users` | Listar usuarios (paginación + búsqueda) |
| GET | `/users/<id>` | Obtener usuario (`?include_tasks=true`) |
| POST | `/users` | Crear usuario |
| PUT | `/users/<id>` | Actualizar usuario |
| DELETE | `/users/<id>` | Soft-delete (`?cascade=true` elimina sus tareas también) |
| POST | `/users/<id>/restore` | Restaurar usuario |
| GET | `/users/<id>/tasks` | Tareas del usuario (paginación + búsqueda) |

### Prueba con cURL

```bash
# Crear usuario
curl -X POST http://127.0.0.1:5000/users \
  -H "Content-Type: application/json" \
  -d '{"username": "juan", "email": "juan@example.com"}'

# Ver usuario con sus tareas
curl "http://127.0.0.1:5000/users/1?include_tasks=true"

# Crear tarea asignada a user 1
curl -X POST http://127.0.0.1:5000/tasks \
  -H "Content-Type: application/json" \
  -d '{"content": "Tarea de Juan", "user_id": 1}'

# Listar tareas de user 1
curl "http://127.0.0.1:5000/users/1/tasks"

# Soft-delete user + sus tareas
curl -X DELETE "http://127.0.0.1:5000/users/1?cascade=true"
```

---

## 5 · Migración a PostgreSQL

**Objetivo:** hacer que la misma aplicación funcione con PostgreSQL cambiando únicamente variables de entorno.

### ¿Por qué funciona sin cambiar el código?

SQLAlchemy actúa como **capa de abstracción**: el mismo código ORM genera SQL válido para MySQL o PostgreSQL. Solo cambia el *driver* y la *URI de conexión*.

### Diferencias clave MySQL vs PostgreSQL

| Aspecto | MySQL | PostgreSQL |
|---|---|---|
| Driver Python | `pymysql` | `psycopg2-binary` |
| Prefijo URI | `mysql+pymysql://` | `postgresql+psycopg2://` |
| Puerto por defecto | 3306 | 5432 |
| `ilike` | Simulado con `LIKE` | Nativo |
| UUID tipo nativo | No (usar `CHAR(36)`) | Sí (`UUID`) |

### Instalar PostgreSQL con Docker

```bash
docker run --name pg-container \
  -e POSTGRES_PASSWORD=my-secret-pw \
  -e POSTGRES_DB=task_db \
  -p 5432:5432 \
  -d postgres:16
```

Conectarse:
```bash
docker exec -it pg-container psql -U postgres -d task_db
```

### Instalar el driver Python

```bash
pip install psycopg2-binary
```

### Cambiar `.env`

Solo hay que modificar cuatro líneas:

```dotenv
DB_ENGINE=postgresql
DB_USER=postgres
DB_PASSWORD=my-secret-pw
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=task_db
```

### `config.py` — lógica de selección

```python
DB_ENGINE = os.getenv("DB_ENGINE", "mysql").lower()

if DB_ENGINE == "postgresql":
    SQLALCHEMY_DATABASE_URI = (
        f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
else:
    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
```

### Inicializar tablas en PostgreSQL

```bash
python db_setup.py
# ✅ Database tables created (or already exist).
```

SQLAlchemy crea las tablas en PostgreSQL exactamente igual que en MySQL — no hace falta cambiar `models.py` ni `app.py`.

---

## Resumen de nuevos endpoints

### Tasks

| Método | URL | Novedad |
|---|---|---|
| GET | `/tasks?page=1&limit=20` | Paginación |
| GET | `/tasks?query=texto` | Búsqueda |
| GET | `/tasks?done=true&user_id=1` | Filtros combinables |
| GET | `/tasks/deleted` | Ver soft-deleted |
| DELETE | `/tasks/<id>` | Soft delete por defecto |
| DELETE | `/tasks/<id>?hard=true` | Hard delete |
| POST | `/tasks/<id>/restore` | Restaurar soft-deleted |

### Users

| Método | URL | Descripción |
|---|---|---|
| GET | `/users` | Listar (paginación + búsqueda) |
| GET | `/users/<id>` | Detalle |
| GET | `/users/<id>?include_tasks=true` | Detalle con tareas |
| POST | `/users` | Crear |
| PUT | `/users/<id>` | Actualizar |
| DELETE | `/users/<id>` | Soft delete |
| DELETE | `/users/<id>?cascade=true` | Soft delete + sus tareas |
| DELETE | `/users/<id>?hard=true` | Hard delete permanente |
| POST | `/users/<id>/restore` | Restaurar |
| GET | `/users/<id>/tasks` | Tareas del usuario |

---

## Estructura final del proyecto

```
flask_task_manager/
├── app.py            ← CRUD tasks + CRUD users (todos los stretch goals)
├── config.py         ← Soporte MySQL y PostgreSQL vía DB_ENGINE
├── models.py         ← Task (soft-delete, user_id FK) + User
├── db_setup.py       ← Crea tablas
├── .env.example      ← Template de variables de entorno
└── requirements.txt  ← pymysql + psycopg2-binary
```