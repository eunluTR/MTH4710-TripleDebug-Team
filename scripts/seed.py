import os
import random
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

from faker import Faker
from werkzeug.security import generate_password_hash

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from app.extensions import db
from app.models import (
    Announcement,
    AuditActorType,
    Club,
    ClubApplication,
    ClubApplicationStatus,
    ClubFounderInvitation,
    ClubManager,
    ClubStatus,
    Event,
    EventRegistration,
    EventRegistrationStatus,
    EventStatus,
    InvitationStatus,
    Membership,
    MembershipApplication,
    MembershipApplicationStatus,
    NotificationType,
    User,
    UserRole,
)
from app.utils import create_notification, log_audit


app = create_app()


def slugify(value):
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", ".", value).strip(".")
    return value or "club"


def seed_admin(session):
    email = os.getenv("ADMIN_EMAIL", "admin@university.edu")
    password = os.getenv("ADMIN_PASSWORD", "AdminPass123")
    name = os.getenv("ADMIN_NAME", "SKS")
    surname = os.getenv("ADMIN_SURNAME", "Admin")

    admin = session.query(User).filter_by(email=email).first()
    if admin:
        return admin, password, False

    admin = User(
        role=UserRole.SKS_ADMIN,
        name=name,
        surname=surname,
        email=email,
        university_id=None,
        password_hash=generate_password_hash(password),
    )
    session.add(admin)
    session.flush()
    return admin, password, True


def seed_students(session, fake, count, password):
    students = []
    for index in range(count):
        student = User(
            role=UserRole.STUDENT,
            name=fake.first_name(),
            surname=fake.last_name(),
            university_id=f"S{10000 + index}",
            email=fake.unique.email(),
            password_hash=generate_password_hash(password),
        )
        students.append(student)
    session.add_all(students)
    session.flush()
    return students


def seed_founder_invites(session, fake, application, students):
    population = [
        student for student in students if student.id != application.applicant_user_id
    ]
    invite_count = min(3, len(population))
    if invite_count == 0:
        return
    invited = random.sample(population, k=invite_count)
    for student in invited:
        status = random.choice(
            [InvitationStatus.INVITED, InvitationStatus.ACCEPTED, InvitationStatus.REJECTED]
        )
        invite = ClubFounderInvitation(
            club_application_id=application.id,
            invited_student_id=student.id,
            status=status,
            responded_at=datetime.utcnow()
            if status != InvitationStatus.INVITED
            else None,
        )
        session.add(invite)
        create_notification(
            student.id,
            NotificationType.FOUNDER_INVITE,
            "Founder Invitation",
            f"You were invited to join the founders list for {application.proposed_name}.",
            related_object_type="ClubApplication",
            related_object_id=application.id,
        )


def seed_club_applications(
    session,
    fake,
    students,
    admin,
    approved_count,
    pending_count,
    rejected_count,
    manager_password,
):
    categories = [
        "Arts",
        "Sports",
        "Tech",
        "Culture",
        "Science",
        "Business",
        "Community",
        "Health",
    ]
    decisions = [
        "Strong proposal with clear objectives.",
        "Not aligned with current campus priorities.",
        "Needs a more detailed activity plan.",
        "Approved pending meeting schedule.",
    ]
    clubs = []
    managers = []
    total = approved_count + pending_count + rejected_count

    for index in range(total):
        applicant = random.choice(students)
        proposed_name = f"{fake.unique.word().title()} {random.choice(['Club', 'Society', 'Association'])}"
        application = ClubApplication(
            applicant_user_id=applicant.id,
            proposed_name=proposed_name,
            proposed_description=fake.paragraph(nb_sentences=4),
            proposed_category=random.choice(categories),
            founders_note=fake.sentence(),
        )
        now = datetime.utcnow()
        if index < approved_count:
            application.status = ClubApplicationStatus.APPROVED
            application.decided_at = now
            application.decided_by_admin_id = admin.id
            application.admin_comment = random.choice(decisions)
        elif index < approved_count + pending_count:
            application.status = ClubApplicationStatus.PENDING
        else:
            application.status = ClubApplicationStatus.REJECTED
            application.decided_at = now
            application.decided_by_admin_id = admin.id
            application.admin_comment = random.choice(decisions)

        session.add(application)
        session.flush()
        seed_founder_invites(session, fake, application, students)

        if application.status == ClubApplicationStatus.APPROVED:
            club_email = f"{slugify(proposed_name)}@clubs.edu"
            club = Club(
                name=proposed_name,
                description=application.proposed_description,
                category=application.proposed_category,
                contact_email=club_email,
                status=ClubStatus.APPROVED,
                approved_at=now,
                applicant_user_id=application.applicant_user_id,
            )
            session.add(club)
            session.flush()
            manager = ClubManager(
                club_id=club.id,
                email=club_email,
                password_hash=generate_password_hash(manager_password),
            )
            session.add(manager)
            clubs.append(club)
            managers.append(manager)

            create_notification(
                application.applicant_user_id,
                NotificationType.CLUB_APP_DECISION,
                "Club Application Approved",
                (
                    f"Your club application '{application.proposed_name}' was approved. "
                    f"Club login: {club_email} | Initial password: {manager_password}"
                ),
                related_object_type="Club",
                related_object_id=club.id,
            )
            log_audit(
                actor_type=AuditActorType.USER_ADMIN,
                actor_id=admin.id,
                action="approve_club_application",
                object_type="ClubApplication",
                object_id=application.id,
                details=application.proposed_name,
            )
        elif application.status == ClubApplicationStatus.REJECTED:
            create_notification(
                application.applicant_user_id,
                NotificationType.CLUB_APP_DECISION,
                "Club Application Rejected",
                f"Your club application '{application.proposed_name}' was rejected.",
                related_object_type="ClubApplication",
                related_object_id=application.id,
            )
            log_audit(
                actor_type=AuditActorType.USER_ADMIN,
                actor_id=admin.id,
                action="reject_club_application",
                object_type="ClubApplication",
                object_id=application.id,
                details=application.admin_comment or "",
            )

    return clubs, managers


def seed_memberships_and_applications(session, fake, clubs, students):
    membership_map = {}
    for club in clubs:
        member_count = min(len(students), random.randint(10, 25))
        members = random.sample(students, member_count)
        membership_map[club.id] = set()
        for student in members:
            session.add(
                Membership(club_id=club.id, user_id=student.id, is_active=True)
            )
            membership_map[club.id].add(student.id)
        session.flush()

        available = [student for student in students if student.id not in membership_map[club.id]]
        random.shuffle(available)
        approved_count = min(len(available), random.randint(4, 10))
        pending_count = min(len(available) - approved_count, random.randint(3, 8))
        rejected_count = min(
            len(available) - approved_count - pending_count, random.randint(2, 6)
        )

        for student in available[:approved_count]:
            application = MembershipApplication(
                club_id=club.id,
                user_id=student.id,
                status=MembershipApplicationStatus.APPROVED,
                decided_at=datetime.utcnow(),
                decided_by_manager_id=club.manager.id,
                decision_reason="Welcome aboard.",
            )
            session.add(application)
            session.flush()
            if student.id not in membership_map[club.id]:
                session.add(
                    Membership(club_id=club.id, user_id=student.id, is_active=True)
                )
                membership_map[club.id].add(student.id)
            create_notification(
                student.id,
                NotificationType.MEMBERSHIP_DECISION,
                "Membership Approved",
                f"Your membership application to {club.name} was approved.",
                related_object_type="MembershipApplication",
                related_object_id=application.id,
            )

        for student in available[approved_count : approved_count + pending_count]:
            session.add(
                MembershipApplication(
                    club_id=club.id,
                    user_id=student.id,
                    status=MembershipApplicationStatus.PENDING,
                    message=fake.sentence(),
                )
            )

        rejected_slice = available[
            approved_count + pending_count : approved_count + pending_count + rejected_count
        ]
        for student in rejected_slice:
            application = MembershipApplication(
                club_id=club.id,
                user_id=student.id,
                status=MembershipApplicationStatus.REJECTED,
                decided_at=datetime.utcnow(),
                decided_by_manager_id=club.manager.id,
                decision_reason="Not a fit right now.",
            )
            session.add(application)
            session.flush()
            create_notification(
                student.id,
                NotificationType.MEMBERSHIP_DECISION,
                "Membership Rejected",
                f"Your membership application to {club.name} was rejected.",
                related_object_type="MembershipApplication",
                related_object_id=application.id,
            )

    return membership_map


def seed_announcements(session, fake, clubs, membership_map):
    for club in clubs:
        for _ in range(random.randint(2, 4)):
            announcement = Announcement(
                club_id=club.id,
                title=fake.sentence(nb_words=6),
                body=fake.paragraph(nb_sentences=4),
                created_by_manager_id=club.manager.id,
            )
            session.add(announcement)
            session.flush()
            for user_id in membership_map.get(club.id, set()):
                create_notification(
                    user_id,
                    NotificationType.ANNOUNCEMENT,
                    f"{club.name} Announcement",
                    announcement.title,
                    related_object_type="Announcement",
                    related_object_id=announcement.id,
                )


def seed_events(session, fake, clubs, students, admin):
    now = datetime.utcnow()
    for club in clubs:
        specs = [
            (EventStatus.APPROVED, now + timedelta(days=random.randint(7, 40))),
            (EventStatus.APPROVED, now - timedelta(days=random.randint(7, 40))),
            (EventStatus.PENDING_APPROVAL, now + timedelta(days=random.randint(10, 50))),
            (EventStatus.REJECTED, now + timedelta(days=random.randint(15, 60))),
        ]
        for status, start_time in specs:
            end_time = start_time + timedelta(hours=random.randint(2, 4))
            capacity = random.choice([None, 25, 40, 60, 80])
            event = Event(
                club_id=club.id,
                title=fake.catch_phrase(),
                description=fake.paragraph(nb_sentences=5),
                location=fake.city(),
                start_datetime=start_time,
                end_datetime=end_time,
                capacity=capacity,
                registration_deadline=start_time - timedelta(days=2),
                status=status,
                created_by_manager_id=club.manager.id,
            )
            if status in {EventStatus.APPROVED, EventStatus.REJECTED}:
                event.admin_comment = random.choice(
                    ["Approved by SKS.", "Needs better safety plan.", "Great impact."]
                )
                event.decided_at = now
                event.approved_by_admin_id = admin.id
            session.add(event)
            session.flush()

            if status == EventStatus.APPROVED:
                create_notification(
                    club.applicant_user_id,
                    NotificationType.EVENT_STATUS,
                    "Event Approved",
                    f"Your event '{event.title}' was approved.",
                    related_object_type="Event",
                    related_object_id=event.id,
                )
                log_audit(
                    actor_type=AuditActorType.USER_ADMIN,
                    actor_id=admin.id,
                    action="approve_event",
                    object_type="Event",
                    object_id=event.id,
                    details=event.title,
                )
            elif status == EventStatus.REJECTED:
                create_notification(
                    club.applicant_user_id,
                    NotificationType.EVENT_STATUS,
                    "Event Rejected",
                    f"Your event '{event.title}' was rejected.",
                    related_object_type="Event",
                    related_object_id=event.id,
                )
                log_audit(
                    actor_type=AuditActorType.USER_ADMIN,
                    actor_id=admin.id,
                    action="reject_event",
                    object_type="Event",
                    object_id=event.id,
                    details=event.admin_comment or "",
                )

            if status == EventStatus.APPROVED:
                possible_attendees = random.sample(
                    students, k=min(len(students), random.randint(8, 20))
                )
                if capacity:
                    possible_attendees = possible_attendees[:capacity]
                for student in possible_attendees:
                    is_cancelled = random.random() < 0.2
                    registration = EventRegistration(
                        event_id=event.id,
                        user_id=student.id,
                        status=EventRegistrationStatus.CANCELLED
                        if is_cancelled
                        else EventRegistrationStatus.REGISTERED,
                        registered_at=now - timedelta(days=random.randint(1, 5)),
                        cancelled_at=now - timedelta(days=random.randint(0, 2))
                        if is_cancelled
                        else None,
                    )
                    session.add(registration)


def seed_demo_data():
    seed_reset = os.getenv("SEED_RESET", "0") == "1"
    student_password = os.getenv("STUDENT_PASSWORD", "StudentPass123")
    manager_password = os.getenv("MANAGER_PASSWORD", "ManagerPass123")
    student_count = int(os.getenv("SEED_STUDENTS", "60"))
    approved_clubs = int(os.getenv("SEED_CLUBS", "8"))
    pending_clubs = int(os.getenv("SEED_PENDING_CLUB_APPS", "2"))
    rejected_clubs = int(os.getenv("SEED_REJECTED_CLUB_APPS", "2"))
    seed_value = int(os.getenv("SEED_RANDOM", "42"))

    fake = Faker()
    Faker.seed(seed_value)
    random.seed(seed_value)

    with app.app_context():
        if seed_reset:
            db.drop_all()
            db.create_all()

        existing_students = User.query.filter_by(role=UserRole.STUDENT).count()
        existing_clubs = Club.query.count()
        if existing_students or existing_clubs:
            print("Demo data already exists. Set SEED_RESET=1 to recreate.")
            return

        admin, admin_password, created = seed_admin(db.session)
        students = seed_students(db.session, fake, student_count, student_password)
        clubs, managers = seed_club_applications(
            db.session,
            fake,
            students,
            admin,
            approved_clubs,
            pending_clubs,
            rejected_clubs,
            manager_password,
        )
        membership_map = seed_memberships_and_applications(db.session, fake, clubs, students)
        seed_announcements(db.session, fake, clubs, membership_map)
        seed_events(db.session, fake, clubs, students, admin)
        db.session.commit()

        if created:
            print(f"Created admin: {admin.email} / {admin_password}")
        print(f"Student login password: {student_password}")
        print(f"Club manager password: {manager_password}")
        print(f"Seeded {len(students)} students, {len(clubs)} clubs, demo data ready.")


if __name__ == "__main__":
    seed_demo_data()
