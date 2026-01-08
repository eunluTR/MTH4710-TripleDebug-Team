from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for, abort, current_app
from flask_login import current_user

from ..extensions import db
from ..forms.student import (
    ClubApplicationForm,
    FounderInviteForm,
    MembershipApplicationForm,
    SimpleSubmitForm,
)
from ..models import (
    Club,
    ClubStatus,
    ClubApplication,
    ClubApplicationStatus,
    ClubFounderInvitation,
    InvitationStatus,
    Membership,
    MembershipApplication,
    MembershipApplicationStatus,
    NotificationType,
    Notification,
    User,
    UserRole,
    Event,
    EventStatus,
    EventRegistration,
    EventRegistrationStatus,
)
from ..rbac import student_required
from ..utils import create_notification, get_page


student_bp = Blueprint("student", __name__)


@student_bp.route("/")
def home():
    if current_user.is_authenticated:
        if hasattr(current_user, "role"):
            return redirect(url_for("student.dashboard"))
        return redirect(url_for("manager.dashboard"))
    return render_template("student/home.html")


@student_bp.route("/dashboard")
@student_required
def dashboard():
    notifications = (
        current_user.notifications.order_by(Notification.created_at.desc()).limit(5).all()
    )
    return render_template("student/dashboard.html", notifications=notifications)


@student_bp.route("/clubs")
@student_required
def clubs():
    page = get_page()
    query = Club.query.filter_by(status=ClubStatus.APPROVED)
    search = request.args.get("q")
    if search:
        like = f"%{search}%"
        query = query.filter(Club.name.ilike(like))
    per_page = current_app.config.get("ITEMS_PER_PAGE", 10)
    pagination = query.order_by(Club.name.asc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return render_template("student/clubs.html", pagination=pagination, search=search)


@student_bp.route("/clubs/<int:club_id>")
@student_required
def club_detail(club_id):
    club = Club.query.filter_by(id=club_id, status=ClubStatus.APPROVED).first_or_404()
    form = MembershipApplicationForm()
    existing_application = MembershipApplication.query.filter(
        MembershipApplication.club_id == club.id,
        MembershipApplication.user_id == current_user.id,
        MembershipApplication.status.in_(
            [MembershipApplicationStatus.PENDING, MembershipApplicationStatus.APPROVED]
        ),
    ).first()
    existing_membership = Membership.query.filter_by(
        club_id=club.id, user_id=current_user.id, is_active=True
    ).first()
    return render_template(
        "student/club_detail.html",
        club=club,
        form=form,
        existing_application=existing_application,
        existing_membership=existing_membership,
    )


@student_bp.route("/clubs/<int:club_id>/apply", methods=["POST"])
@student_required
def apply_membership(club_id):
    club = Club.query.filter_by(id=club_id, status=ClubStatus.APPROVED).first_or_404()
    form = MembershipApplicationForm()
    if not form.validate_on_submit():
        flash("Unable to submit application.", "error")
        return redirect(url_for("student.club_detail", club_id=club.id))

    if Membership.query.filter_by(
        club_id=club.id, user_id=current_user.id, is_active=True
    ).first():
        flash("You are already a member of this club.", "info")
        return redirect(url_for("student.club_detail", club_id=club.id))

    existing = MembershipApplication.query.filter(
        MembershipApplication.club_id == club.id,
        MembershipApplication.user_id == current_user.id,
        MembershipApplication.status.in_(
            [MembershipApplicationStatus.PENDING, MembershipApplicationStatus.APPROVED]
        ),
    ).first()
    if existing:
        flash("You already have an active application.", "info")
        return redirect(url_for("student.club_detail", club_id=club.id))

    application = MembershipApplication(
        club_id=club.id,
        user_id=current_user.id,
        message=form.message.data,
    )
    db.session.add(application)
    db.session.commit()
    flash("Application submitted.", "success")
    return redirect(url_for("student.my_clubs"))


@student_bp.route("/me/clubs")
@student_required
def my_clubs():
    memberships = Membership.query.filter_by(user_id=current_user.id, is_active=True).all()
    applications = MembershipApplication.query.filter_by(user_id=current_user.id).order_by(
        MembershipApplication.created_at.desc()
    )
    return render_template(
        "student/my_clubs.html", memberships=memberships, applications=applications
    )


@student_bp.route("/club-applications/new", methods=["GET", "POST"])
@student_required
def new_club_application():
    form = ClubApplicationForm()
    if form.validate_on_submit():
        existing = ClubApplication.query.filter_by(
            applicant_user_id=current_user.id, status=ClubApplicationStatus.PENDING
        ).first()
        if existing:
            flash("You already have a pending club application.", "info")
            return redirect(url_for("student.club_application_detail", app_id=existing.id))

        application = ClubApplication(
            applicant_user_id=current_user.id,
            proposed_name=form.proposed_name.data,
            proposed_description=form.proposed_description.data,
            proposed_category=form.proposed_category.data,
            founders_note=form.founders_note.data,
        )
        db.session.add(application)
        db.session.commit()
        flash("Club application submitted.", "success")
        return redirect(url_for("student.club_application_detail", app_id=application.id))

    return render_template("student/club_application_new.html", form=form)


@student_bp.route("/club-applications/<int:app_id>")
@student_required
def club_application_detail(app_id):
    application = ClubApplication.query.filter_by(
        id=app_id, applicant_user_id=current_user.id
    ).first_or_404()
    founders = application.founders.all()
    return render_template(
        "student/club_application_detail.html", application=application, founders=founders
    )


@student_bp.route("/club-applications/<int:app_id>/founders", methods=["GET", "POST"])
@student_required
def manage_founders(app_id):
    application = ClubApplication.query.filter_by(
        id=app_id, applicant_user_id=current_user.id
    ).first_or_404()
    if application.status != ClubApplicationStatus.PENDING:
        flash("Founders list is locked after a decision.", "info")
        return redirect(url_for("student.club_application_detail", app_id=application.id))

    form = FounderInviteForm()
    if form.validate_on_submit():
        invited = User.query.filter_by(email=form.invited_email.data.lower()).first()
        if not invited or invited.role != UserRole.STUDENT:
            flash("Student not found.", "error")
            return redirect(url_for("student.manage_founders", app_id=application.id))
        existing = ClubFounderInvitation.query.filter_by(
            club_application_id=application.id,
            invited_student_id=invited.id,
        ).first()
        if existing:
            flash("Student already invited.", "info")
            return redirect(url_for("student.manage_founders", app_id=application.id))
        invite = ClubFounderInvitation(
            club_application_id=application.id,
            invited_student_id=invited.id,
        )
        db.session.add(invite)
        create_notification(
            invited.id,
            NotificationType.FOUNDER_INVITE,
            "Founder Invitation",
            f"You were invited to join the founders list for {application.proposed_name}.",
            related_object_type="ClubApplication",
            related_object_id=application.id,
        )
        db.session.commit()
        flash("Founder invited.", "success")
        return redirect(url_for("student.manage_founders", app_id=application.id))

    founders = application.founders.all()
    return render_template(
        "student/club_application_founders.html",
        application=application,
        founders=founders,
        form=form,
    )


@student_bp.route("/club-applications/<int:app_id>/founders/<int:invite_id>/remove", methods=["POST"])
@student_required
def remove_founder(app_id, invite_id):
    application = ClubApplication.query.filter_by(
        id=app_id, applicant_user_id=current_user.id
    ).first_or_404()
    invite = ClubFounderInvitation.query.filter_by(
        id=invite_id, club_application_id=application.id
    ).first_or_404()
    if application.status != ClubApplicationStatus.PENDING:
        abort(403)
    db.session.delete(invite)
    db.session.commit()
    flash("Founder removed.", "info")
    return redirect(url_for("student.manage_founders", app_id=application.id))


@student_bp.route("/founder-invitations")
@student_required
def founder_invitations():
    invites = ClubFounderInvitation.query.filter_by(
        invited_student_id=current_user.id
    ).order_by(ClubFounderInvitation.id.desc())
    form = SimpleSubmitForm()
    return render_template("student/founder_invitations.html", invites=invites, form=form)


@student_bp.route("/founder-invitations/<int:invite_id>/accept", methods=["POST"])
@student_required
def accept_invite(invite_id):
    invite = ClubFounderInvitation.query.filter_by(
        id=invite_id, invited_student_id=current_user.id
    ).first_or_404()
    if invite.status != InvitationStatus.INVITED:
        flash("Invitation already responded to.", "info")
        return redirect(url_for("student.founder_invitations"))
    invite.status = InvitationStatus.ACCEPTED
    invite.responded_at = datetime.utcnow()
    application = invite.club_application
    create_notification(
        application.applicant_user_id,
        NotificationType.FOUNDER_RESPONSE,
        "Founder Invitation Accepted",
        f"{current_user.name} {current_user.surname} accepted your founder invite.",
        related_object_type="ClubApplication",
        related_object_id=application.id,
    )
    db.session.commit()
    flash("Invitation accepted.", "success")
    return redirect(url_for("student.founder_invitations"))


@student_bp.route("/founder-invitations/<int:invite_id>/reject", methods=["POST"])
@student_required
def reject_invite(invite_id):
    invite = ClubFounderInvitation.query.filter_by(
        id=invite_id, invited_student_id=current_user.id
    ).first_or_404()
    if invite.status != InvitationStatus.INVITED:
        flash("Invitation already responded to.", "info")
        return redirect(url_for("student.founder_invitations"))
    invite.status = InvitationStatus.REJECTED
    invite.responded_at = datetime.utcnow()
    application = invite.club_application
    create_notification(
        application.applicant_user_id,
        NotificationType.FOUNDER_RESPONSE,
        "Founder Invitation Rejected",
        f"{current_user.name} {current_user.surname} rejected your founder invite.",
        related_object_type="ClubApplication",
        related_object_id=application.id,
    )
    db.session.commit()
    flash("Invitation rejected.", "info")
    return redirect(url_for("student.founder_invitations"))


@student_bp.route("/events")
@student_required
def events():
    page = get_page()
    query = Event.query.filter_by(status=EventStatus.APPROVED)
    club_id = request.args.get("club_id")
    if club_id and club_id.isdigit():
        query = query.filter_by(club_id=int(club_id))
    per_page = current_app.config.get("ITEMS_PER_PAGE", 10)
    pagination = query.order_by(Event.start_datetime.asc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return render_template("student/events.html", pagination=pagination)


@student_bp.route("/events/<int:event_id>")
@student_required
def event_detail(event_id):
    event = Event.query.filter_by(id=event_id, status=EventStatus.APPROVED).first_or_404()
    registration = EventRegistration.query.filter_by(
        event_id=event.id, user_id=current_user.id
    ).first()
    form = SimpleSubmitForm()
    return render_template(
        "student/event_detail.html",
        event=event,
        registration=registration,
        form=form,
    )


@student_bp.route("/events/<int:event_id>/register", methods=["POST"])
@student_required
def register_event(event_id):
    event = Event.query.filter_by(id=event_id, status=EventStatus.APPROVED).first_or_404()
    now = datetime.utcnow()
    if event.registration_deadline and now > event.registration_deadline:
        flash("Registration deadline has passed.", "error")
        return redirect(url_for("student.event_detail", event_id=event.id))
    if now > event.start_datetime:
        flash("Event has already started.", "error")
        return redirect(url_for("student.event_detail", event_id=event.id))
    if event.is_full:
        flash("Event is full.", "error")
        return redirect(url_for("student.event_detail", event_id=event.id))

    registration = EventRegistration.query.filter_by(
        event_id=event.id, user_id=current_user.id
    ).first()
    if registration and registration.status == EventRegistrationStatus.REGISTERED:
        flash("You are already registered.", "info")
        return redirect(url_for("student.event_detail", event_id=event.id))

    if registration:
        registration.status = EventRegistrationStatus.REGISTERED
        registration.registered_at = datetime.utcnow()
        registration.cancelled_at = None
    else:
        registration = EventRegistration(event_id=event.id, user_id=current_user.id)
        db.session.add(registration)

    db.session.commit()
    flash("Registered for event.", "success")
    return redirect(url_for("student.event_detail", event_id=event.id))


@student_bp.route("/events/<int:event_id>/cancel", methods=["POST"])
@student_required
def cancel_event(event_id):
    event = Event.query.filter_by(id=event_id, status=EventStatus.APPROVED).first_or_404()
    registration = EventRegistration.query.filter_by(
        event_id=event.id, user_id=current_user.id
    ).first_or_404()
    if registration.status != EventRegistrationStatus.REGISTERED:
        flash("Registration already cancelled.", "info")
        return redirect(url_for("student.event_detail", event_id=event.id))

    registration.status = EventRegistrationStatus.CANCELLED
    registration.cancelled_at = datetime.utcnow()
    db.session.commit()
    flash("Registration cancelled.", "info")
    return redirect(url_for("student.event_detail", event_id=event.id))


@student_bp.route("/notifications", methods=["GET", "POST"])
@student_required
def notifications():
    form = SimpleSubmitForm()
    if form.validate_on_submit():
        notification_id = request.form.get("notification_id")
        if notification_id and notification_id.isdigit():
            note = current_user.notifications.filter_by(id=int(notification_id)).first()
            if note:
                note.is_read = True
                db.session.commit()
        return redirect(url_for("student.notifications"))

    notifications = current_user.notifications.order_by(
        Notification.created_at.desc()
    ).all()
    return render_template(
        "student/notifications.html", notifications=notifications, form=form
    )


@student_bp.route("/profile")
@student_required
def profile():
    return render_template("student/profile.html")
