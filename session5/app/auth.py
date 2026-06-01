import os
import secrets
from urllib.parse import urlencode

import jwt
import requests
from flask import Blueprint, current_app, redirect, request, session, url_for, jsonify

from app.extensions import db, limiter
from app.models import User

auth_bp = Blueprint("auth", __name__)

AUTH_URL  = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
JWKS_URL  = "https://www.googleapis.com/oauth2/v3/certs"
SCOPE     = "openid email profile"


def _cfg(name):
    return os.environ[name]


@auth_bp.route("/login")
@limiter.limit("10/minute")
def login():
    state = secrets.token_urlsafe(16)
    session["oauth_state"] = state

    params = {
        "response_type": "code",
        "client_id":     _cfg("GOOGLE_CLIENT_ID"),
        "redirect_uri":  _cfg("GOOGLE_REDIRECT_URI"),
        "scope":         SCOPE,
        "state":         state,
        "prompt":        "select_account",
    }
    return redirect(f"{AUTH_URL}?{urlencode(params)}")


@auth_bp.route("/oauth/callback")
def callback():
    # 1. CSRF check
    if request.args.get("state") != session.pop("oauth_state", None):
        return "Invalid state", 400
    if "error" in request.args:
        return f"OAuth error: {request.args['error']}", 400

    # 2. Exchange code -> tokens (server-to-server, with client_secret)
    token_resp = requests.post(TOKEN_URL, data={
        "code":          request.args["code"],
        "client_id":     _cfg("GOOGLE_CLIENT_ID"),
        "client_secret": _cfg("GOOGLE_CLIENT_SECRET"),
        "redirect_uri":  _cfg("GOOGLE_REDIRECT_URI"),
        "grant_type":    "authorization_code",
    }, timeout=10)
    token_resp.raise_for_status()
    tokens = token_resp.json()

    # 3. Verify id_token signature against Google's public keys
    id_token = tokens["id_token"]
    jwks_client = jwt.PyJWKClient(JWKS_URL)
    signing_key = jwks_client.get_signing_key_from_jwt(id_token).key
    claims = jwt.decode(
        id_token,
        signing_key,
        algorithms=["RS256"],
        audience=_cfg("GOOGLE_CLIENT_ID"),
        issuer="https://accounts.google.com",
    )

    # 4. Upsert user
    user = User.query.filter_by(google_sub=claims["sub"]).first()
    if user is None:
        user = User(google_sub=claims["sub"])
        db.session.add(user)

    user.email       = claims["email"]
    user.name        = claims.get("name", "")
    user.picture_url = claims.get("picture", "")
    db.session.commit()

    # 5. Issue local session
    session["user_id"] = user.id
    return redirect(url_for("api.list_notes"))


@auth_bp.route("/logout")
def logout():
    session.clear()
    return jsonify({"message": "logged out"})


@auth_bp.route("/dev/login", methods=["POST"])
def dev_login():
    if not current_app.debug:
        return jsonify({"error": "not available"}), 404
    email = (request.get_json() or {}).get("email")
    if not email:
        return jsonify({"error": "email required"}), 400
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"error": "user not found — log in via browser first"}), 404
    session["user_id"] = user.id
    return jsonify({"message": "ok", "user_id": user.id, "email": user.email})


@auth_bp.route("/me")
def me():
    uid = session.get("user_id")
    if not uid:
        return jsonify({"error": "not authenticated"}), 401
    u = db.session.get(User, uid)
    return jsonify({
        "id":      u.id,
        "email":   u.email,
        "name":    u.name,
        "picture": u.picture_url,
    })
