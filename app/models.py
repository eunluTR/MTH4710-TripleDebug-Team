import enum
from datetime import datetime

from flask_login import UserMixin

from .extensions import db


class UserRole(enum.Enum):
    STUDENT = "STUDENT"
    SKS_ADMIN = "SKS_ADMIN"


class ClubStatus(enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    INACTIVE = "INACTIVE"


class ClubApplicationStatus(enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class InvitationStatus(enum.Enum):
    INVITED = "INVITED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class MembershipApplicationStatus(enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class EventStatus(enum.Enum):
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class EventRegistrationStatus(enum.Enum):
    REGISTERED = "REGISTERED"
    CANCELLED = "CANCELLED"


class NotificationType(enum.Enum):
    MEMBERSHIP_DECISION = "MEMBERSHIP_DECISION"
    ANNOUNCEMENT = "ANNOUNCEMENT"
    CLUB_APP_DECISION = "CLUB_APP_DECISION"
    EVENT_STATUS = "EVENT_STATUS"
    FOUNDER_INVITE = "FOUNDER_INVITE"
    FOUNDER_RESPONSE = "FOUNDER_RESPONSE"


class AuditActorType(enum.Enum):
    USER_ADMIN = "USER_ADMIN"
    CLUB_MANAGER = "CLUB_MANAGER"


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.Enum(UserRole), nullable=False, default=UserRole.STUDENT)
    name = db.Column(db.String(120), nullable=False)
    surname = db.Column(db.String(120), nullable=False)
    university_id = db.Column(db.String(50), unique=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    club_applications = db.relationship(
        "ClubApplication",
        back_populates="applicant",
        foreign_keys="ClubApplication.applicant_user_id",
        lazy="dynamic",
    )
    memberships = db.relationship("Membership", back_populates="user", lazy="dynamic")
    membership_applications = db.relationship(
        "MembershipApplication", back_populates="user", lazy="dynamic"
    )
    notifications = db.relationship(
        "Notification", back_populates="user", lazy="dynamic"
    )

    def get_id(self):
        return f"user:{self.id}"

    @property
    def is_admin(self):
        return self.role == UserRole.SKS_ADMIN


class Club(db.Model):
    __tablename__ = "clubs"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(120))
    logo_url = db.Column(db.String(255))
    contact_email = db.Column(db.String(255))
    status = db.Column(db.Enum(ClubStatus), nullable=False, default=ClubStatus.PENDING)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    approved_at = db.Column(db.DateTime)
    rejected_at = db.Column(db.DateTime)
    applicant_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    manager = db.relationship("ClubManager", back_populates="club", uselist=False)
    memberships = db.relationship("Membership", back_populates="club", lazy="dynamic")
    membership_applications = db.relationship(
        "MembershipApplication", back_populates="club", lazy="dynamic"
    )
    announcements = db.relationship(
        "Announcement", back_populates="club", lazy="dynamic"
    )
    events = db.relationship("Event", back_populates="club", lazy="dynamic")


class ClubManager(UserMixin, db.Model):
    __tablename__ = "club_managers"

    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey("clubs.id"), unique=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    club = db.relationship("Club", back_populates="manager")

    def get_id(self):
        return f"manager:{self.id}"


class ClubApplication(db.Model):
    __tablename__ = "club_applications"

    id = db.Column(db.Integer, primary_key=True)
    applicant_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    proposed_name = db.Column(db.String(200), nullable=False)
    proposed_description = db.Column(db.Text, nullable=False)
    proposed_category = db.Column(db.String(120))
    founders_note = db.Column(db.Text)
    status = db.Column(
        db.Enum(ClubApplicationStatus), nullable=False, default=ClubApplicationStatus.PENDING
    )
    admin_comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    decided_at = db.Column(db.DateTime)
    decided_by_admin_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    applicant = db.relationship(
        "User",
        back_populates="club_applications",
        foreign_keys=[applicant_user_id],
    )
    decided_by_admin = db.relationship("User", foreign_keys=[decided_by_admin_id])
    founders = db.relationship(
        "ClubFounderInvitation", back_populates="club_application", lazy="dynamic"
    )


class ClubFounderInvitation(db.Model):
    __tablename__ = "club_founder_invitations"

    id = db.Column(db.Integer, primary_key=True)
    club_application_id = db.Column(
        db.Integer, db.ForeignKey("club_applications.id"), nullable=False
    )
    invited_student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(db.Enum(InvitationStatus), nullable=False, default=InvitationStatus.INVITED)
    responded_at = db.Column(db.DateTime)

    club_application = db.relationship("ClubApplication", back_populates="founders")
    invited_student = db.relationship("User")


class Membership(db.Model):
    __tablename__ = "memberships"

    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey("clubs.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    is_active = db.Column(db.Boolean, default=True)

    club = db.relationship("Club", back_populates="memberships")
    user = db.relationship("User", back_populates="memberships")

    __table_args__ = (
        db.UniqueConstraint("club_id", "user_id", name="uniq_membership"),
    )


class MembershipApplication(db.Model):
    __tablename__ = "membership_applications"

    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey("clubs.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(
        db.Enum(MembershipApplicationStatus),
        nullable=False,
        default=MembershipApplicationStatus.PENDING,
    )
    message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    decided_at = db.Column(db.DateTime)
    decided_by_manager_id = db.Column(db.Integer, db.ForeignKey("club_managers.id"))
    decision_reason = db.Column(db.Text)

    club = db.relationship("Club", back_populates="membership_applications")
    user = db.relationship("User", back_populates="membership_applications")
    decided_by_manager = db.relationship("ClubManager")


class Announcement(db.Model):
    __tablename__ = "announcements"

    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey("clubs.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_by_manager_id = db.Column(db.Integer, db.ForeignKey("club_managers.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    club = db.relationship("Club", back_populates="announcements")
    created_by_manager = db.relationship("ClubManager")


class Event(db.Model):
    __tablename__ = "events"

    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey("clubs.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    location = db.Column(db.String(200), nullable=False)
    start_datetime = db.Column(db.DateTime, nullable=False)
    end_datetime = db.Column(db.DateTime, nullable=False)
    capacity = db.Column(db.Integer)
    registration_deadline = db.Column(db.DateTime)
    status = db.Column(db.Enum(EventStatus), nullable=False, default=EventStatus.PENDING_APPROVAL)
    created_by_manager_id = db.Column(db.Integer, db.ForeignKey("club_managers.id"))
    admin_comment = db.Column(db.Text)
    approved_by_admin_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    decided_at = db.Column(db.DateTime)

    club = db.relationship("Club", back_populates="events")
    created_by_manager = db.relationship("ClubManager")
    approved_by_admin = db.relationship("User")
    registrations = db.relationship(
        "EventRegistration", back_populates="event", lazy="dynamic"
    )

    @property
    def registration_count(self):
        return (
            self.registrations.filter_by(status=EventRegistrationStatus.REGISTERED).count()
        )

    @property
    def is_full(self):
        if self.capacity is None:
            return False
        return self.registration_count >= self.capacity


class EventRegistration(db.Model):
    __tablename__ = "event_registrations"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(
        db.Enum(EventRegistrationStatus),
        nullable=False,
        default=EventRegistrationStatus.REGISTERED,
    )
    registered_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    cancelled_at = db.Column(db.DateTime)

    event = db.relationship("Event", back_populates="registrations")
    user = db.relationship("User")

    __table_args__ = (
        db.UniqueConstraint("event_id", "user_id", name="uniq_event_registration"),
    )


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    type = db.Column(db.Enum(NotificationType), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    related_object_type = db.Column(db.String(100))
    related_object_id = db.Column(db.Integer)

    user = db.relationship("User", back_populates="notifications")


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    actor_type = db.Column(db.Enum(AuditActorType), nullable=False)
    actor_id = db.Column(db.Integer, nullable=False)
    action = db.Column(db.String(200), nullable=False)
    object_type = db.Column(db.String(100), nullable=False)
    object_id = db.Column(db.Integer, nullable=False)
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
