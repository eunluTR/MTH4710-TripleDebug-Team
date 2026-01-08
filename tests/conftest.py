import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models import User, UserRole


@pytest.fixture()
def app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def admin_user(app):
    with app.app_context():
        admin = User(
            role=UserRole.SKS_ADMIN,
            name="Admin",
            surname="User",
            email="admin@example.com",
            password_hash=generate_password_hash("AdminPass123"),
        )
        db.session.add(admin)
        db.session.commit()
        return admin
