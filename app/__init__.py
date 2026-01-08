import logging
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler

from flask import Flask, redirect, request, url_for
from flask_login import current_user

from .extensions import db, migrate, login_manager, csrf
from .models import User, ClubManager, UserRole


def create_app(config_name=None):
    app = Flask(__name__, instance_relative_config=True)

    config_name = config_name or os.getenv("APP_ENV", "development")
    config_map = {
        "development": "config.DevelopmentConfig",
        "production": "config.ProductionConfig",
        "testing": "config.TestingConfig",
    }
    app.config.from_object(config_map.get(config_name, "config.DevelopmentConfig"))

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    configure_logging(app)

    login_manager.login_view = "auth.login"
    login_manager.session_protection = "strong"

    @login_manager.user_loader
    def load_user(user_id):
        if not user_id:
            return None
        if user_id.startswith("user:"):
            raw_id = user_id.split(":", 1)[1]
            if raw_id.isdigit():
                return db.session.get(User, int(raw_id))
        if user_id.startswith("manager:"):
            raw_id = user_id.split(":", 1)[1]
            if raw_id.isdigit():
                return db.session.get(ClubManager, int(raw_id))
        return None

    @login_manager.unauthorized_handler
    def unauthorized():
        if request.blueprint == "manager":
            return redirect(url_for("manager.login", next=request.full_path))
        return redirect(url_for("auth.login", next=request.full_path))

    @app.context_processor
    def inject_globals():
        role = None
        if isinstance(current_user._get_current_object(), User):
            role = current_user.role
        return {
            "current_role": role,
            "is_manager": isinstance(current_user._get_current_object(), ClubManager),
            "UserRole": UserRole,
        }

    from .blueprints.auth import auth_bp
    from .blueprints.student import student_bp
    from .blueprints.manager import manager_bp
    from .blueprints.admin import admin_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(student_bp)
    app.register_blueprint(manager_bp, url_prefix="/manager")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    register_error_handlers(app)

    return app


def configure_logging(app):
    if app.testing:
        return
    log_dir = Path(app.instance_path)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"

    handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    handler.setFormatter(formatter)

    if not any(isinstance(existing, RotatingFileHandler) for existing in app.logger.handlers):
        app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)


def register_error_handlers(app):
    from flask import render_template

    @app.errorhandler(403)
    def forbidden(error):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(error):
        return render_template("errors/500.html"), 500
