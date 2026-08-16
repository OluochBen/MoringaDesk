import datetime
import time

from flask_jwt_extended import create_access_token

from app import db
from app.models.user import User
from app.routes.auth import _safe_redirect_url


def _register(client, email="student@example.com", **extra):
    payload = {
        "name": "Student User",
        "email": email,
        "password": "secret123",
        **extra,
    }
    return client.post("/auth/register", json=payload)


def test_public_registration_rejects_admin_role(client):
    response = _register(client, email="no-admin@example.com", role="admin")

    assert response.status_code == 400
    assert "role" in response.get_json()["error"].lower()
    assert User.query.filter_by(email="no-admin@example.com").first() is None


def test_public_registration_rejects_unknown_role(client):
    response = _register(client, email="no-owner@example.com", role="owner")

    assert response.status_code == 400
    assert User.query.filter_by(email="no-owner@example.com").first() is None


def test_public_registration_always_creates_student(client):
    response = _register(client, email="student-only@example.com", role="student")

    assert response.status_code == 201
    assert response.get_json()["user"]["role"] == "student"


def test_unsafe_oauth_redirect_falls_back_to_allowlisted_url(app):
    with app.test_request_context():
        app.config["SOCIAL_DEFAULT_REDIRECT"] = "http://localhost:5173/auth/callback"
        app.config["OAUTH_REDIRECT_ALLOWLIST"] = {
            "http://localhost:5173/auth/callback"
        }

        assert _safe_redirect_url("https://attacker.example/steal") == (
            "http://localhost:5173/auth/callback"
        )
        assert _safe_redirect_url("http://localhost:5173/auth/callback") == (
            "http://localhost:5173/auth/callback"
        )


def test_student_cannot_access_admin_routes(client):
    registration = _register(client, email="ordinary@example.com")
    token = registration.get_json()["access_token"]

    response = client.get(
        "/admin/users", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403


def test_admin_route_rejects_missing_jwt(client):
    assert client.get("/admin/users").status_code == 401


def test_expired_jwt_is_rejected(client, app):
    with app.app_context():
        token = create_access_token(
            identity="1", expires_delta=datetime.timedelta(seconds=-1)
        )

    response = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401


def test_invalid_jwt_is_rejected(client):
    response = client.get(
        "/auth/me", headers={"Authorization": "Bearer not-a-valid-jwt"}
    )

    assert response.status_code == 422


def test_oauth_exchange_rejects_invalid_and_expired_codes(client):
    with client.session_transaction() as oauth_session:
        oauth_session["oauth_exchange"] = {
            "code": "expected-code",
            "user_id": 1,
            "expires_at": int(time.time()) + 60,
        }
    assert client.post(
        "/auth/oauth/exchange", json={"code": "wrong-code"}
    ).status_code == 401

    with client.session_transaction() as oauth_session:
        oauth_session["oauth_exchange"] = {
            "code": "expired-code",
            "user_id": 1,
            "expires_at": int(time.time()) - 1,
        }
    assert client.post(
        "/auth/oauth/exchange", json={"code": "expired-code"}
    ).status_code == 401


def test_oauth_exchange_is_single_use(client):
    user = User(name="OAuth User", email="oauth@example.com", role="student")
    user.set_password("unused-password")
    db.session.add(user)
    db.session.commit()

    with client.session_transaction() as oauth_session:
        oauth_session["oauth_exchange"] = {
            "code": "one-time-code",
            "user_id": user.id,
            "expires_at": int(time.time()) + 60,
        }

    first = client.post("/auth/oauth/exchange", json={"code": "one-time-code"})
    second = client.post("/auth/oauth/exchange", json={"code": "one-time-code"})

    assert first.status_code == 200
    assert first.get_json()["access_token"]
    assert second.status_code == 401
