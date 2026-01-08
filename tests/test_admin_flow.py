from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import ClubApplication, ClubApplicationStatus, Club, ClubManager, User, UserRole


def test_admin_approves_club_application(client, app):
    with app.app_context():
        admin = User(
            role=UserRole.SKS_ADMIN,
            name="Admin",
            surname="User",
            email="admin@example.com",
            password_hash=generate_password_hash("AdminPass123"),
        )
        student = User(
            role=UserRole.STUDENT,
            name="Student",
            surname="User",
            email="student@example.com",
            university_id="S98765",
            password_hash=generate_password_hash("Password123"),
        )
        db.session.add_all([admin, student])
        db.session.commit()
        application = ClubApplication(
            applicant_user_id=student.id,
            proposed_name="Chess Club",
            proposed_description="Play chess",
            proposed_category="Games",
        )
        db.session.add(application)
        db.session.commit()
        application_id = application.id

    client.post(
        "/auth/login",
        data={"email": "admin@example.com", "password": "AdminPass123"},
        follow_redirects=True,
    )

    response = client.post(
        f"/admin/club-applications/{application_id}",
        data={
            "decision": "approve",
            "admin_comment": "Looks good",
            "club_email": "chess@clubs.edu",
            "initial_password": "TempPass123",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        club = Club.query.filter_by(name="Chess Club").first()
        manager = ClubManager.query.filter_by(email="chess@clubs.edu").first()
        assert club is not None
        assert manager is not None
        assert ClubApplication.query.first().status == ClubApplicationStatus.APPROVED
