from flask import Flask, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_socketio import SocketIO
from authlib.integrations.flask_client import OAuth
import os
from dotenv import load_dotenv


db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
socketio = SocketIO()
oauth = OAuth()


def create_app():
    app = Flask(__name__)
    load_dotenv()

    # --- Database ---
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        base_dir = os.path.abspath(os.path.dirname(__file__))
        db_path = os.path.join(base_dir, "..", "instance", "app.db")
        db_url = f"sqlite:///{db_path}"
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)

    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    environment = os.getenv("FLASK_ENV", "development").lower()
    is_production = environment == "production" or os.getenv("RENDER", "").lower() == "true"

    secret_key = os.getenv("SECRET_KEY")
    jwt_secret_key = os.getenv("JWT_SECRET_KEY")
    if is_production and (not secret_key or not jwt_secret_key):
        missing = [
            name
            for name, value in (("SECRET_KEY", secret_key), ("JWT_SECRET_KEY", jwt_secret_key))
            if not value
        ]
        raise RuntimeError(f"Missing required production secrets: {', '.join(missing)}")

    app.config["SECRET_KEY"] = secret_key or "dev-secret-key"
    app.config["JWT_SECRET_KEY"] = jwt_secret_key or "jwt-secret"
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SECURE"] = is_production
    app.config["SESSION_COOKIE_SAMESITE"] = "None" if is_production else "Lax"

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    socketio.init_app(
        app,
        cors_allowed_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "https://moringadesk-gcvu.onrender.com",
            "https://moringadesk-gteo.onrender.com",
        ],
    )
    oauth.init_app(app)
    app.config.setdefault(
        "SOCIAL_DEFAULT_REDIRECT",
        os.getenv("SOCIAL_DEFAULT_REDIRECT", "http://localhost:5173/auth/callback"),
    )
    configured_redirects = os.getenv("OAUTH_REDIRECT_ALLOWLIST", "")
    app.config["OAUTH_REDIRECT_ALLOWLIST"] = {
        url.strip().rstrip("/")
        for url in configured_redirects.split(",")
        if url.strip()
    } or {
        "http://localhost:5173/auth/callback",
        "http://127.0.0.1:5173/auth/callback",
        "https://moringadesk-gcvu.onrender.com/auth/callback",
        "https://moringadesk-gteo.onrender.com/auth/callback",
    }
    register_oauth_clients(app)

    # --- CORS ---
    CORS(
        app,
        resources={
            r"/*": {
                "origins": [
                    "http://localhost:5173",
                    "http://127.0.0.1:5173",
                    "https://moringadesk-gcvu.onrender.com",
                    "https://moringadesk-gteo.onrender.com",
                ]
            }
        },
        supports_credentials=True,
        allow_headers=["Content-Type", "Authorization"],
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    )

    # --- Blueprints ---
    from .routes.public import public_bp
    from .routes.auth import auth_bp
    from .routes.problems import problems_bp
    from .routes.faqs import faqs_bp
    from .routes.admin import admin_bp
    from .routes.solutions import solutions_bp
    from .routes.notifications import notifications_bp
    from .routes.tags import tags_bp
    from .routes.profile import profile_bp
    from .routes.blog import blog_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(problems_bp, url_prefix="/problems")
    app.register_blueprint(faqs_bp, url_prefix="/faqs")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(solutions_bp, url_prefix="/solutions")
    app.register_blueprint(notifications_bp, url_prefix="/notifications")
    app.register_blueprint(tags_bp, url_prefix="/tags")
    app.register_blueprint(profile_bp, url_prefix="/profile")
    app.register_blueprint(blog_bp, url_prefix="/blog")

    # --- WebSocket events ---
    try:
        from . import events  # noqa: F401
    except ImportError:
        pass

    # --- Health check ---
    @app.route("/ping", methods=["GET", "OPTIONS"])
    def ping():
        return {"status": "ok"}, 200

    # --- Frontend fallback (for SPA routes) ---
    frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))

    if os.path.isdir(frontend_dist):
        @app.route("/", defaults={"path": ""}, methods=["GET"])
        @app.route("/<path:path>", methods=["GET"])
        def serve_frontend(path):
            """Serve built frontend files with index.html fallback."""
            target = os.path.join(frontend_dist, path)
            if path and os.path.isfile(target):
                return send_from_directory(frontend_dist, path)
            return send_from_directory(frontend_dist, "index.html")

    return app


def register_oauth_clients(app):
    google_client_id = os.getenv("GOOGLE_CLIENT_ID")
    google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    if google_client_id and google_client_secret:
        oauth.register(
            name="google",
            client_id=google_client_id,
            client_secret=google_client_secret,
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )

    github_client_id = os.getenv("GITHUB_CLIENT_ID")
    github_client_secret = os.getenv("GITHUB_CLIENT_SECRET")
    if github_client_id and github_client_secret:
        oauth.register(
            name="github",
            client_id=github_client_id,
            client_secret=github_client_secret,
            access_token_url="https://github.com/login/oauth/access_token",
            authorize_url="https://github.com/login/oauth/authorize",
            api_base_url="https://api.github.com/",
            client_kwargs={"scope": "read:user user:email"},
        )

    facebook_client_id = os.getenv("FACEBOOK_CLIENT_ID")
    facebook_client_secret = os.getenv("FACEBOOK_CLIENT_SECRET")
    if facebook_client_id and facebook_client_secret:
        oauth.register(
            name="facebook",
            client_id=facebook_client_id,
            client_secret=facebook_client_secret,
            access_token_url="https://graph.facebook.com/v13.0/oauth/access_token",
            authorize_url="https://www.facebook.com/v13.0/dialog/oauth",
            api_base_url="https://graph.facebook.com/v13.0/",
            client_kwargs={"scope": "email"},
        )
