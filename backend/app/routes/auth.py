import base64
import json
import secrets
import datetime
import time
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from flask import Blueprint, request, jsonify, current_app, redirect, url_for, session
from flask_cors import cross_origin
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity

from .. import db, oauth
from ..models.user import User


auth_bp = Blueprint("auth", __name__)


def _handle_preflight():
    """Return an empty 204 for preflight requests."""
    return ("", 204)


# --- Register ---
@auth_bp.route("/register", methods=["POST", "OPTIONS"])
@cross_origin()
def register():
    if request.method == "OPTIONS":
        return _handle_preflight()

    data = request.get_json() or {}

    name = data.get("name")
    email = data.get("email")
    password = data.get("password")
    requested_role = data.get("role")

    if not name or not email or not password:
        return jsonify({"error": "Name, email, and password are required"}), 400

    if requested_role not in (None, "student"):
        return jsonify({"error": "Role cannot be assigned during public registration"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 400

    user = User(name=name, email=email, role="student")
    user.set_password(password)

    db.session.add(user)
    db.session.commit()

    # issue token
    access_token = create_access_token(identity=str(user.id), expires_delta=datetime.timedelta(hours=1))

    return jsonify({
        "access_token": access_token,
        "user": user.to_dict()
    }), 201


# --- Login ---
@auth_bp.route("/login", methods=["POST", "OPTIONS"])
@cross_origin()
def login():
    if request.method == "OPTIONS":
        return _handle_preflight()

    data = request.get_json() or {}
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid credentials"}), 401

    access_token = create_access_token(identity=str(user.id), expires_delta=datetime.timedelta(hours=1))

    return jsonify({
        "access_token": access_token,
        "user": user.to_dict()
    }), 200


# --- Current User ---
@auth_bp.route("/me", methods=["GET", "OPTIONS"])
@cross_origin()
@jwt_required()
def me():
    if request.method == "OPTIONS":
        return _handle_preflight()

    user_id = get_jwt_identity()
    try:
        user_id = int(user_id)  # convert back to int
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid token"}), 422

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify({"user": user.to_dict()}), 200


def _encode_state(payload):
    data = json.dumps(payload).encode("utf-8")
    return base64.urlsafe_b64encode(data).decode("utf-8")


def _decode_state(raw):
    if not raw:
        return {}
    try:
        padded = raw + "=" * (-len(raw) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")
        return json.loads(decoded)
    except Exception:
        return {}


def _safe_redirect_url(candidate):
    default_url = current_app.config.get("SOCIAL_DEFAULT_REDIRECT")
    allowed = current_app.config.get("OAUTH_REDIRECT_ALLOWLIST", set())
    normalized = candidate.rstrip("/") if candidate else None
    if normalized in allowed:
        return candidate
    return default_url if default_url and default_url.rstrip("/") in allowed else next(iter(allowed), None)


def _append_query_params(url, params):
    parsed = urlparse(url)
    existing = dict(parse_qsl(parsed.query, keep_blank_values=True))
    for key, value in params.items():
        if value is not None:
            existing[key] = value
    new_query = urlencode(existing)
    return urlunparse(parsed._replace(query=new_query))


def _social_profile(provider, client, token):
    provider = provider.lower()
    if provider == "google":
        userinfo = client.userinfo(token=token)
        return {
            "email": userinfo.get("email"),
            "name": userinfo.get("name") or userinfo.get("given_name"),
        }

    if provider == "github":
        profile_resp = client.get("user", token=token)
        profile_resp.raise_for_status()
        profile_data = profile_resp.json()
        email = profile_data.get("email")
        if not email:
            emails_resp = client.get("user/emails", token=token)
            if emails_resp.ok:
                for entry in emails_resp.json():
                    if entry.get("primary") and entry.get("verified"):
                        email = entry.get("email")
                        break
                if not email:
                    emails = emails_resp.json()
                    if emails:
                        email = emails[0].get("email")
        return {
            "email": email,
            "name": profile_data.get("name") or profile_data.get("login"),
        }

    if provider == "facebook":
        profile_resp = client.get("me?fields=id,name,email", token=token)
        profile_resp.raise_for_status()
        profile_data = profile_resp.json()
        return {
            "email": profile_data.get("email"),
            "name": profile_data.get("name"),
        }

    raise ValueError(f"Unsupported provider: {provider}")


def _get_or_create_user(name, email):
    user = User.query.filter_by(email=email).first()
    if user:
        if name and user.name != name:
            user.name = name
        return user, False

    user = User(name=name or email.split("@")[0], email=email, role="student")
    user.set_password(secrets.token_urlsafe(32))
    db.session.add(user)
    return user, True


@auth_bp.route("/oauth/<provider>", methods=["GET"])
def oauth_start(provider):
    client = oauth.create_client(provider)
    if not client:
        return jsonify({"error": f"Unsupported provider '{provider}'"}), 404

    redirect_url = _safe_redirect_url(request.args.get("redirect_url"))
    intent = request.args.get("intent", "login")
    frontend_state = request.args.get("state")

    state_payload = {
        "redirect_url": redirect_url,
        "intent": intent,
        "frontend_state": frontend_state,
        "nonce": secrets.token_urlsafe(8),
        "provider": provider,
    }

    callback_url = url_for("auth.oauth_callback", provider=provider, _external=True)
    encoded_state = _encode_state(state_payload)

    extra_params = {}
    if provider == "google":
        extra_params["prompt"] = "select_account"

    return client.authorize_redirect(callback_url, state=encoded_state, **extra_params)


@auth_bp.route("/oauth/<provider>/callback", methods=["GET"])
def oauth_callback(provider):
    client = oauth.create_client(provider)
    if not client:
        return jsonify({"error": f"Unsupported provider '{provider}'"}), 404

    raw_state = request.args.get("state")
    state_payload = _decode_state(raw_state)
    redirect_url = _safe_redirect_url(state_payload.get("redirect_url"))
    intent = state_payload.get("intent")
    frontend_state = state_payload.get("frontend_state")

    try:
        token = client.authorize_access_token()
    except Exception as exc:
        current_app.logger.exception("OAuth token exchange failed for %s", provider)
        error_redirect = _append_query_params(
            redirect_url,
            {
                "error": "Unable to authenticate with provider. Please try again.",
                "provider": provider,
            },
        )
        return redirect(error_redirect)

    try:
        profile = _social_profile(provider, client, token)
    except Exception as exc:
        current_app.logger.exception("Failed to fetch profile from %s: %s", provider, exc)
        error_redirect = _append_query_params(
            redirect_url,
            {
                "error": "Unable to retrieve your profile information from the provider.",
                "provider": provider,
            },
        )
        return redirect(error_redirect)

    email = profile.get("email")
    name = profile.get("name")
    if not email:
        error_redirect = _append_query_params(
            redirect_url,
            {
                "error": "Your account does not have an accessible email address.",
                "provider": provider,
            },
        )
        return redirect(error_redirect)

    try:
        user, created = _get_or_create_user(name, email)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("Failed to persist user for %s: %s", provider, exc)
        error_redirect = _append_query_params(
            redirect_url,
            {
                "error": "Unable to finalize your account. Please contact support.",
                "provider": provider,
            },
        )
        return redirect(error_redirect)

    exchange_code = secrets.token_urlsafe(32)
    session["oauth_exchange"] = {
        "code": exchange_code,
        "user_id": user.id,
        "expires_at": int(time.time()) + 90,
    }
    success_redirect = _append_query_params(
        redirect_url,
        {
            "code": exchange_code,
            "provider": provider,
            "intent": intent,
            "state": frontend_state,
        },
    )
    return redirect(success_redirect)


@auth_bp.route("/oauth/exchange", methods=["POST", "OPTIONS"])
@cross_origin(supports_credentials=True)
def oauth_exchange():
    if request.method == "OPTIONS":
        return _handle_preflight()

    supplied_code = (request.get_json() or {}).get("code")
    exchange = session.pop("oauth_exchange", None)
    if (
        not supplied_code
        or not exchange
        or exchange.get("expires_at", 0) < int(time.time())
        or not secrets.compare_digest(supplied_code, exchange.get("code", ""))
    ):
        return jsonify({"error": "Invalid or expired OAuth exchange code"}), 401

    user = db.session.get(User, exchange.get("user_id"))
    if not user:
        return jsonify({"error": "User not found"}), 404

    access_token = create_access_token(
        identity=str(user.id), expires_delta=datetime.timedelta(hours=1)
    )
    return jsonify({"access_token": access_token, "user": user.to_dict()}), 200
