from datetime import datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_user, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db
from ..forms.auth import RegisterForm, LoginForm
from ..models import User, UserRole


auth_bp = Blueprint("auth", __name__)

LOGIN_ATTEMPTS = {}
MAX_ATTEMPTS = 5
WINDOW_SECONDS = 300


def _rate_limited(ip_address):
    now = datetime.utcnow()
    window_start = now - timedelta(seconds=WINDOW_SECONDS)
    attempts = LOGIN_ATTEMPTS.get(ip_address, [])
    attempts = [ts for ts in attempts if ts > window_start]
    LOGIN_ATTEMPTS[ip_address] = attempts
    return len(attempts) >= MAX_ATTEMPTS


def _record_attempt(ip_address):
    LOGIN_ATTEMPTS.setdefault(ip_address, []).append(datetime.utcnow())


def _login_redirect(user):
    if user.role == UserRole.SKS_ADMIN:
        return redirect(url_for("admin.dashboard"))
    return redirect(url_for("student.dashboard"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("student.dashboard"))
    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data.lower()
        if User.query.filter((User.email == email) | (User.university_id == form.university_id.data)).first():
            flash("Email or student number already in use.", "error")
            return render_template("auth/register.html", form=form)

        user = User(
            role=UserRole.STUDENT,
            name=form.name.data.strip(),
            surname=form.surname.data.strip(),
            university_id=form.university_id.data.strip(),
            email=email,
            password_hash=generate_password_hash(form.password.data),
        )
        db.session.add(user)
        db.session.commit()
        flash("Account created. Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        if hasattr(current_user, "role"):
            return _login_redirect(current_user)
        return redirect(url_for("manager.dashboard"))

    form = LoginForm()
    ip_address = request.remote_addr or "unknown"
    if form.validate_on_submit():
        if _rate_limited(ip_address):
            flash("Too many login attempts. Try again later.", "error")
            return render_template("auth/login.html", form=form)

        email = form.email.data.lower()
        user = User.query.filter_by(email=email).first()
        if user and user.is_active and check_password_hash(user.password_hash, form.password.data):
            login_user(user)
            return _login_redirect(user)

        _record_attempt(ip_address)
        flash("Invalid credentials.", "error")

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
def logout():
    logout_user()
    flash("Logged out.", "info")
    return redirect(url_for("auth.login"))
