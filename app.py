"""Application factory and development entry point for Rickshaw Share."""
import os
from pathlib import Path
from flask import Flask, session
from auth_routes import register_auth_routes
from database import db
from models import User
from ride_routes import register_ride_routes

ROOT = Path(__file__).resolve().parent
DEFAULT_DATABASE = ROOT / "instance" / "rickshaw_share.db"


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-change-me"),
        SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL", f"sqlite:///{DEFAULT_DATABASE}"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    if test_config:
        app.config.update(test_config)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    db.init_app(app)
    register_auth_routes(app)
    register_ride_routes(app)

    @app.context_processor
    def inject_current_user():
        user_id = session.get("user_id")
        return {"current_user": db.session.get(User, user_id) if user_id else None}

    with app.app_context():
        db.create_all()
    return app


app = create_app()

if __name__ == "__main__":
    if os.environ.get("FLASK_DEBUG") == "1":
        # Keep Flask's auto-reloader available during active development.
        app.run(debug=True)
    else:
        # Waitress is a production-grade WSGI server and works well on Windows.
        from waitress import serve

        host = os.environ.get("HOST", "127.0.0.1")
        port = int(os.environ.get("PORT", "5000"))
        print(f"Rickshaw Share is running at http://{host}:{port}")
        serve(app, host=host, port=port)
