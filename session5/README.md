# Notes API

REST API de notas personales con autenticación OAuth 2.0 via Google. Cada usuario solo puede ver y gestionar sus propias notas.

## Integrantes
- Leonardo Pachari Gomez
- Nicolle Lozano Vega
- Katherine Saico Ccahuana
- Elias Manchego Navarro
- Piero Poblete Andía

## Stack

- **Flask** — framework web
- **Flask-SQLAlchemy** — ORM
- **SQLite** — base de datos local (`instance/notes.db`)
- **PyJWT** — verificación del ID token de Google
- **python-dotenv** — variables de entorno

## Estructura del proyecto

```
notes_api/
├── app/
│   ├── __init__.py       # Factory de la app Flask
│   ├── auth.py           # Rutas de autenticación OAuth 2.0
│   ├── api.py            # Endpoints de notas
│   ├── models.py         # Modelos User y Note
│   └── extensions.py     # Instancia de SQLAlchemy
├── run.py                # Punto de entrada
├── requirements.txt
└── .env
```

## Configuración

Crear un archivo `.env` en la raíz del proyecto:

```env
GOOGLE_CLIENT_ID=<tu_client_id>
GOOGLE_CLIENT_SECRET=<tu_client_secret>
GOOGLE_REDIRECT_URI=http://localhost:5000/oauth/callback
FLASK_SECRET_KEY=<clave_secreta_para_firmar_sesiones>
DATABASE_URI=sqlite:///notes.db
```

### Obtener credenciales de Google

1. [Google Cloud Console](https://console.cloud.google.com) → APIs & Services → Credentials
2. Crear credencial → OAuth 2.0 Client ID → Web application
3. Authorized redirect URIs → agregar `http://localhost:5000/oauth/callback`
4. Copiar Client ID y Client Secret al `.env`

## Instalación y ejecución

```bash
pip install -r requirements.txt
python run.py
```

La base de datos se crea automáticamente en `instance/notes.db` al iniciar.

## Flujo de autenticación

La app implementa el flujo **Authorization Code** de OAuth 2.0:

```
Usuario → GET /login → Google consent screen → GET /oauth/callback → sesión activa
```

1. `/login` genera un `state` aleatorio, lo guarda en sesión y redirige a Google
2. El usuario autoriza el acceso en Google
3. Google redirige a `/oauth/callback` con un `code`
4. El servidor verifica el `state` (protección CSRF), intercambia el `code` por tokens con Google (server-to-server), valida la firma del `id_token` usando las claves públicas de Google (JWKS), y crea o actualiza el usuario en la DB
5. Se guarda `user_id` en la sesión Flask (cookie firmada)

## Endpoints

### Autenticación

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/login` | Inicia el flujo OAuth con Google (PKCE + offline access) |
| GET | `/oauth/callback` | Callback de Google, crea la sesión y persiste el refresh token |
| GET | `/logout` | Cierra la sesión |
| GET | `/me` | Datos del usuario autenticado |
| POST | `/refresh` | Obtiene un nuevo access token de Google (requiere sesión) |
| POST | `/api/token` | Emite un JWT Bearer desde la sesión activa |

### Notas (requieren sesión Flask **o** Bearer JWT)

| Método | Ruta | Descripción | Rol |
|--------|------|-------------|-----|
| GET | `/api/notes` | Lista todas las notas del usuario | any |
| POST | `/api/notes` | Crea una nota nueva | any |
| DELETE | `/api/notes/:id` | Elimina una nota por ID | any |
| GET | `/api/admin/notes` | Lista todas las notas de todos los usuarios | `admin` |

#### POST `/api/notes` — body esperado

```json
{
  "title": "Título de la nota",
  "body": "Contenido opcional"
}
```

## Modelos de datos

**User**
| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | Integer | PK autoincremental |
| google_sub | String | ID único de Google (sub del id_token) |
| email | String | Email de la cuenta Google |
| name | String | Nombre del usuario |
| picture_url | String | URL de la foto de perfil |
| created_at | DateTime | Fecha de registro |

**Note**
| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | Integer | PK autoincremental |
| user_id | Integer | FK a User |
| title | String | Título (obligatorio) |
| body | Text | Contenido |
| created_at | DateTime | Fecha de creación |

## Cómo probar con Postman

### Paso 1 — Login

En el request de login, tab **Authorization**:

| Campo | Valor |
|-------|-------|
| Type | OAuth 2.0 |
| Grant Type | Authorization Code |
| Callback URL | `http://localhost:5000/oauth/callback` |
| Auth URL | `https://accounts.google.com/o/oauth2/v2/auth` |
| Access Token URL | `https://oauth2.googleapis.com/token` |
| Client ID | valor de `GOOGLE_CLIENT_ID` en `.env` |
| Client Secret | valor de `GOOGLE_CLIENT_SECRET` en `.env` |
| Scope | `openid email profile` |
| Client Authentication | Send as Basic Auth header |

Marcar **Authorize using browser** y click en **Get New Access Token**. Se abrirá el browser para completar el login con Google.

### Paso 2 — Verificar sesión

```
GET http://localhost:5000/me
```

Debe devolver el email y nombre del usuario autenticado.

### Paso 3 — Usar los endpoints

Postman guarda la cookie `session` automáticamente en su Cookie Jar. Todos los requests siguientes a `/api/notes` la enviarán sin configuración adicional.

---

## Mejoras de seguridad implementadas

### 11.5 Rate Limiting

Protege los endpoints más sensibles contra abuso y enumeración de cuentas usando **Flask-Limiter**.

**Dependencia añadida:** `Flask-Limiter==3.5.0`

**Límites activos:**

| Endpoint | Límite |
|----------|--------|
| `GET /login` | 10 req / minuto por IP |
| `POST /api/notes` | 30 req / minuto por IP |
| Resto de endpoints | 200 req / día · 60 req / hora (global) |

Cuando se supera el límite, Flask-Limiter responde automáticamente con `429 Too Many Requests`.

**Archivos modificados:** `app/extensions.py`, `app/__init__.py`, `app/auth.py`, `app/api.py`

---

### 11.1 Refresh Token Support

Los access tokens de Google expiran en **1 hora**. Con un `refresh_token` almacenado, el servidor puede obtener uno nuevo sin que el usuario tenga que volver a iniciar sesión.

**Cambios en el modelo `User`:**

| Campo nuevo | Tipo | Descripción |
|-------------|------|-------------|
| `refresh_token` | String(512) | Token de larga duración emitido por Google |

**Cambios en el flujo OAuth:**
- `/login` ahora solicita `access_type=offline` y `prompt=consent` para garantizar que Google entregue el `refresh_token`
- `/oauth/callback` persiste el `refresh_token` en la base de datos cada vez que Google lo incluye

**Nuevo endpoint:**

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/refresh` | Obtiene un nuevo `access_token` usando el `refresh_token` almacenado (requiere sesión activa) |

**Respuesta de `/refresh`:**
```json
{ "access_token": "ya29.nuevo_token..." }
```

> En producción, el `refresh_token` debe almacenarse cifrado (por ejemplo con `cryptography.fernet`).

**Archivos modificados:** `app/models.py`, `app/auth.py`

---

### 11.4 Role-Based Access Control (RBAC)

La autenticación responde *¿quién eres?*; la autorización responde *¿qué puedes hacer?*. Se añade un sistema de roles para proteger endpoints administrativos sin necesidad de un servicio separado.

**Roles disponibles:**

| Rol | Valor en DB | Descripción |
|-----|-------------|-------------|
| `user` | `"user"` | Rol por defecto para todo nuevo registro |
| `admin` | `"admin"` | Acceso a endpoints de administración |

**Campo añadido al modelo `User`:**

| Campo | Tipo | Default |
|-------|------|---------|
| `role` | String(16) | `"user"` |

**Nuevo decorator `roles_required`** en `app/api.py`:

```python
@api_bp.route("/admin/notes")
@login_required
@roles_required(Role.admin)
def admin_list_all_notes():
    ...
```

Devuelve `403 Forbidden` si el usuario no tiene el rol requerido.

**Nuevo endpoint:**

| Método | Ruta | Descripción | Rol requerido |
|--------|------|-------------|---------------|
| GET | `/api/admin/notes` | Lista todas las notas de todos los usuarios | `admin` |

**Asignar rol admin (Flask shell):**

```python
from app.models import User, Role
from app.extensions import db
u = User.query.filter_by(email="tu@gmail.com").first()
u.role = Role.admin
db.session.commit()
```

**Archivos modificados:** `app/models.py`, `app/api.py`

---

### 11.2 PKCE — Proof Key for Code Exchange

PKCE es obligatorio en **OAuth 2.1** y protege contra el robo del `authorization code` en tránsito. Incluso si un atacante intercepta el `code`, no puede canjearlo por tokens porque no tiene el `code_verifier` original.

**Cómo funciona:**

```
CLIENTE                              GOOGLE
  │                                     │
  │  1. genera code_verifier (random)   │
  │     SHA-256 → code_challenge        │
  │                                     │
  │── /authorize?code_challenge=... ──► │
  │◄── authorization code ─────────────│
  │                                     │
  │── /token  code + code_verifier ───► │
  │           Google hace SHA-256       │
  │           y compara con el hash     │
  │◄── access_token ───────────────────│
```

**¿Por qué no está activo en este laboratorio?**

Google rechaza `code_verifier` en el token exchange cuando el cliente OAuth es de tipo **Web application (confidential)** con `client_secret`. PKCE está pensado para **clientes públicos** (SPAs, apps móviles) que no pueden mantener un secreto. En un servidor web con `client_secret`, el canal server-to-server ya garantiza la misma protección. Google requiere habilitarlo explícitamente en la consola para clientes confidenciales.

**Implementación de referencia** (para cuando se migre a cliente público / OAuth 2.1):

```python
# En /login — generar verifier y challenge
code_verifier  = secrets.token_urlsafe(64)
code_challenge = base64.urlsafe_b64encode(
    hashlib.sha256(code_verifier.encode()).digest()
).rstrip(b"=").decode()
session["code_verifier"] = code_verifier

params["code_challenge"]        = code_challenge
params["code_challenge_method"] = "S256"

# En /callback — enviar verifier al token endpoint
data["code_verifier"] = session.pop("code_verifier", "")
```

> Para apps de escritorio o móviles sin `client_secret`, PKCE es la **única** protección posible.

**Estado:** documentado, no activo (incompatible con cliente confidencial de Google sin configuración adicional en Cloud Console)

---

### 11.3 JWTs propios (API sin estado)

Permite que clientes API (SPAs, apps móviles) usen `Authorization: Bearer <token>` en lugar de cookies de sesión. Ambos mecanismos coexisten: el navegador sigue usando sesión y los clientes API usan JWT.

**Tradeoffs clave:**

| | Sesión Flask (cookie) | JWT propio |
|---|---|---|
| Almacenamiento | Servidor (cookie firmada) | Cliente (memoria / localStorage) |
| Revocación | Inmediata (`session.clear()`) | Imposible hasta expiración |
| Escalabilidad | Requiere sesión compartida | Sin estado — cualquier réplica lo valida |
| Riesgo XSS | Bajo (HttpOnly cookie) | Alto si se guarda en `localStorage` |

**Nuevo endpoint:**

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/api/token` | Intercambia la sesión activa por un JWT Bearer |

**Respuesta de `/api/token`:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

**Uso desde cualquier cliente HTTP:**
```bash
# 1. Obtener el JWT (requiere sesión activa previa)
TOKEN=$(curl -s -X POST http://localhost:5000/api/token \
  -H "Cookie: session=<cookie>" | jq -r .access_token)

# 2. Usar el JWT en requests posteriores (sin cookies)
curl http://localhost:5000/api/notes \
  -H "Authorization: Bearer $TOKEN"

curl -X POST http://localhost:5000/api/notes \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "nota via JWT"}'
```

El decorador `login_required` acepta automáticamente **ambos** mecanismos: primero intenta el Bearer JWT, si no existe cae en la sesión Flask.

**Archivos modificados:** `app/auth.py`, `app/api.py`

---

### Endpoint de desarrollo rápido

Disponible únicamente cuando la app corre con `debug=True`:

```
POST http://localhost:5000/dev/login
Content-Type: application/json

{ "email": "tu@gmail.com" }
```

Inicia sesión directamente para agilizar las pruebas durante el desarrollo sin repetir el flujo del browser cada vez.
