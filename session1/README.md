# Flask Session 01 — Task & User Manager API

Laboratorio de introducción a Flask: construcción de una API REST con operaciones CRUD completas para **tareas** y **usuarios**, conectada a un frontend en HTML/CSS/JS puro.

> **Curso:** Desarrollo Web Backend  
> **Universidad:** Universidad La Salle Arequipa  
> **Herramientas:** Python 3.11 · Flask · Anaconda · Postman

---

## Estructura del proyecto

```
flask_session01/
├── app.py                                   # API REST con Flask
├── index.html                               # Frontend (HTML + CSS + JS)
├── flask_session01.postman_collection.json  # Colección de tests Postman
└── README.md
```

---

## Instalación y ejecución

### 1. Crear y activar el entorno con Anaconda

```bash
conda create --name flask_env python=3.11
conda activate flask_env
```

### 2. Instalar dependencias

```bash
pip install flask flask-cors
```

### 3. Iniciar el servidor

```bash
python app.py
```

El servidor quedará disponible en `http://127.0.0.1:5000`

### 4. Abrir el frontend

Abre el archivo `index.html` directamente en el navegador (doble clic). No requiere servidor adicional.

---

## Endpoints de la API

### Tasks — `/tasks`

| Método   | Ruta              | Descripción                         | Body (JSON)                         |
|----------|-------------------|-------------------------------------|-------------------------------------|
| `GET`    | `/tasks`          | Listar todas las tareas             | —                                   |
| `GET`    | `/tasks/<id>`     | Obtener una tarea por ID            | —                                   |
| `POST`   | `/tasks`          | Crear nueva tarea                   | `{ "content": "texto" }`            |
| `PUT`    | `/tasks/<id>`     | Actualizar contenido y/o estado     | `{ "content": "...", "done": true }`|
| `DELETE` | `/tasks/<id>`     | Eliminar tarea                      | —                                   |

**Ejemplo — crear tarea:**
```json
POST /tasks
{
  "content": "Estudiar Flask"
}
```

**Respuesta:**
```json
{
  "message": "Task added!",
  "task": { "id": 1, "content": "Estudiar Flask", "done": false }
}
```

---

### Users — `/users`

| Método   | Ruta              | Descripción                        | Body (JSON)          |
|----------|-------------------|------------------------------------|----------------------|
| `GET`    | `/users`          | Listar todos los usuarios          | —                    |
| `GET`    | `/users/<id>`     | Obtener un usuario por ID          | —                    |
| `POST`   | `/users`          | Crear nuevo usuario                | Ver estructura abajo |
| `PUT`    | `/users/<id>`     | Actualizar usuario                 | Ver estructura abajo |
| `DELETE` | `/users/<id>`     | Eliminar usuario                   | —                    |

**Estructura de usuario:**
```json
{
  "name": "Pablo",
  "lastname": "Gonzales",
  "address": {
    "city": "Arequipa",
    "country": "Perú",
    "code": "04000"
  }
}
```

---

## Testing con Postman

1. Abrir **Postman**
2. Click en **Import** (esquina superior izquierda)
3. Seleccionar `flask_session01.postman_collection.json`
4. Click **Import**
5. La colección aparecerá con dos carpetas: `Tasks` y `Users`
6. Asegurarse de tener el servidor corriendo antes de ejecutar los requests

La colección incluye casos de validación (tarea vacía, usuario con campos faltantes) que deben retornar error `400`.

---

## Funcionalidades implementadas

- [x] `GET /tasks` — listar todas las tareas
- [x] `GET /tasks/<id>` — obtener tarea por ID
- [x] `POST /tasks` — crear tarea con validación (no permite contenido vacío)
- [x] `PUT /tasks/<id>` — actualizar contenido y marcar como completada (`done: true/false`)
- [x] `DELETE /tasks/<id>` — eliminar tarea
- [x] CRUD completo de Users con dirección anidada (`city`, `country`, `code`)
- [x] Validación de campos obligatorios en Tasks y Users
- [x] Frontend conectado al backend con HTML, CSS y JavaScript puro
- [x] Colección Postman con todos los endpoints y casos de error