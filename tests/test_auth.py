from app.models import User


def test_register_and_login(client, app):
    response = client.post(
        "/auth/register",
        data={
            "name": "Ada",
            "surname": "Lovelace",
            "university_id": "S12345",
            "email": "ada@example.com",
            "password": "Password123",
            "confirm": "Password123",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        assert User.query.filter_by(email="ada@example.com").first() is not None

    response = client.post(
        "/auth/login",
        data={"email": "ada@example.com", "password": "Password123"},
        follow_redirects=True,
    )
    assert b"Student Dashboard" in response.data
