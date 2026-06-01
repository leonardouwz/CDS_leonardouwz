# Notes API

REST API de notas personales con autenticación OAuth 2.0 via Google. Cada usuario solo puede ver y gestionar sus propias notas.

## Stack

- **Flask** — framework web
- **Flask-SQLAlchemy** — ORM
- **SQLite** — base de datos local (`instance/notes.db`)
- **PyJWT** — verificación del ID token de Google
- **python-dotenv** — variables de entorno

## Estructura del proyecto

```
session5/
├── app/
│   ├── __init__.py       # Factory de la app Flask
│   ├── auth.py           # Rutas de autenticación OAuth 2.0
│   ├── api.py            # Endpoints de notas
│   ├── models.py         # Modelos User y Note
│   └── extensions.py     # Instancia de SQLAlchemy
├── run.py                # Punto de entrada
├── requirements.txt
└── .env                  # No incluido — usar .env.example como base
```

## Configuración

Copiar `.env.example` a `.env` y completar con las credenciales reales:

```env
GOOGLE_CLIENT_ID=your_client_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-your_secret
GOOGLE_REDIRECT_URI=http://localhost:5000/oauth/callback
FLASK_SECRET_KEY=replace-me-with-a-random-string
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
| GET | `/login` | Inicia el flujo OAuth con Google |
| GET | `/oauth/callback` | Callback de Google, crea la sesión |
| GET | `/logout` | Cierra la sesión |
| GET | `/me` | Datos del usuario autenticado |

### Notas (requieren sesión activa)

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/notes` | Lista todas las notas del usuario |
| POST | `/api/notes` | Crea una nota nueva |
| DELETE | `/api/notes/:id` | Elimina una nota por ID |

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

### Endpoint de desarrollo rápido

Disponible únicamente cuando la app corre con `debug=True`:

```
POST http://localhost:5000/dev/login
Content-Type: application/json

{ "email": "tu@gmail.com" }
```

Inicia sesión directamente para agilizar las pruebas durante el desarrollo sin repetir el flujo del browser cada vez.
