import secrets
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, url_for, abort
from flask_login import current_user
from werkzeug.security import generate_password_hash

from ..extensions import db
from ..forms.admin import ClubDecisionForm, EventDecisionForm
from ..models import (
    ClubApplication,
    ClubApplicationStatus,
    Club,
    ClubStatus,
    ClubManager,
    AuditActorType,
    Event,
    EventStatus,
    NotificationType,
)
from ..rbac import admin_required
from ..utils import create_notification, log_audit


admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/login")
def login():
    return redirect(url_for("auth.login"))


@admin_bp.route("/logout")
@admin_required
def logout():
    return redirect(url_for("auth.logout"))


@admin_bp.route("/dashboard")
@admin_required
def dashboard():
    pending_clubs = ClubApplication.query.filter_by(
        status=ClubApplicationStatus.PENDING
    ).count()
    pending_events = Event.query.filter_by(status=EventStatus.PENDING_APPROVAL).count()
    return render_template(
        "admin/dashboard.html",
        pending_clubs=pending_clubs,
        pending_events=pending_events,
    )


@admin_bp.route("/club-applications")
@admin_required
def club_applications():
    pending = ClubApplication.query.filter_by(
        status=ClubApplicationStatus.PENDING
    ).order_by(ClubApplication.created_at.desc())
    decided = ClubApplication.query.filter(
        ClubApplication.status != ClubApplicationStatus.PENDING
    ).order_by(ClubApplication.decided_at.desc())
    return render_template(
        "admin/club_applications.html", pending=pending, decided=decided
    )


@admin_bp.route("/club-applications/<int:application_id>", methods=["GET", "POST"])
@admin_required
def club_application_detail(application_id):
    application = db.session.get(ClubApplication, application_id)
    if not application:
        abort(404)
    form = ClubDecisionForm()
    if form.validate_on_submit():
        if application.status != ClubApplicationStatus.PENDING:
            flash("Application already decided.", "info")
            return redirect(url_for("admin.club_applications"))
        application.admin_comment = form.admin_comment.data
        application.decided_at = datetime.utcnow()
        application.decided_by_admin_id = current_user.id

        if form.decision.data == "approve":
            if Club.query.filter_by(name=application.proposed_name).first():
                flash("A club with that name already exists.", "error")
                return redirect(url_for("admin.club_application_detail", application_id=application.id))
            club_email = form.club_email.data or f"{application.proposed_name.lower().replace(' ', '.')}@clubs.edu"
            raw_password = form.initial_password.data or secrets.token_urlsafe(8)
            if ClubManager.query.filter_by(email=club_email).first():
                flash("Club email already in use.", "error")
                return redirect(url_for("admin.club_application_detail", application_id=application.id))

            club = Club(
                name=application.proposed_name,
                description=application.proposed_description,
                category=application.proposed_category,
                contact_email=club_email,
                status=ClubStatus.APPROVED,
                approved_at=datetime.utcnow(),
                applicant_user_id=application.applicant_user_id,
            )
            db.session.add(club)
            db.session.flush()
            manager = ClubManager(
                club_id=club.id,
                email=club_email,
                password_hash=generate_password_hash(raw_password),
            )
            db.session.add(manager)
            application.status = ClubApplicationStatus.APPROVED

            create_notification(
                application.applicant_user_id,
                NotificationType.CLUB_APP_DECISION,
                "Club Application Approved",
                (
                    f"Your club application '{application.proposed_name}' was approved. "
                    f"Club login: {club_email} | Initial password: {raw_password}"
                ),
                related_object_type="Club",
                related_object_id=club.id,
            )
            log_audit(
                actor_type=AuditActorType.USER_ADMIN,
                actor_id=current_user.id,
                action="approve_club_application",
                object_type="ClubApplication",
                object_id=application.id,
                details=application.proposed_name,
            )
        else:
            application.status = ClubApplicationStatus.REJECTED
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
                actor_id=current_user.id,
                action="reject_club_application",
                object_type="ClubApplication",
                object_id=application.id,
                details=form.admin_comment.data or "",
            )

        db.session.commit()
        flash("Decision recorded.", "success")
        return redirect(url_for("admin.club_applications"))

    return render_template(
        "admin/club_application_detail.html",
        application=application,
        form=form,
    )


@admin_bp.route("/events/proposals")
@admin_required
def event_proposals():
    pending = Event.query.filter_by(status=EventStatus.PENDING_APPROVAL).order_by(
        Event.created_at.desc()
    )
    decided = Event.query.filter(Event.status != EventStatus.PENDING_APPROVAL).order_by(
        Event.decided_at.desc()
    )
    return render_template("admin/event_proposals.html", pending=pending, decided=decided)


@admin_bp.route("/events/proposals/<int:event_id>", methods=["GET", "POST"])
@admin_required
def event_proposal_detail(event_id):
    event = db.session.get(Event, event_id)
    if not event:
        abort(404)
    form = EventDecisionForm()
    if form.validate_on_submit():
        if event.status != EventStatus.PENDING_APPROVAL:
            flash("Event already decided.", "info")
            return redirect(url_for("admin.event_proposals"))
        event.admin_comment = form.admin_comment.data
        event.decided_at = datetime.utcnow()
        event.approved_by_admin_id = current_user.id
        if form.decision.data == "approve":
            event.status = EventStatus.APPROVED
            create_notification(
                event.club.applicant_user_id,
                NotificationType.EVENT_STATUS,
                "Event Approved",
                f"Your event '{event.title}' was approved.",
                related_object_type="Event",
                related_object_id=event.id,
            )
            log_audit(
                actor_type=AuditActorType.USER_ADMIN,
                actor_id=current_user.id,
                action="approve_event",
                object_type="Event",
                object_id=event.id,
                details=event.title,
            )
        else:
            event.status = EventStatus.REJECTED
            create_notification(
                event.club.applicant_user_id,
                NotificationType.EVENT_STATUS,
                "Event Rejected",
                f"Your event '{event.title}' was rejected.",
                related_object_type="Event",
                related_object_id=event.id,
            )
            log_audit(
                actor_type=AuditActorType.USER_ADMIN,
                actor_id=current_user.id,
                action="reject_event",
                object_type="Event",
                object_id=event.id,
                details=form.admin_comment.data or "",
            )

        db.session.commit()
        flash("Decision recorded.", "success")
        return redirect(url_for("admin.event_proposals"))

    return render_template("admin/event_proposal_detail.html", event=event, form=form)


@admin_bp.route("/clubs")
@admin_required
def clubs():
    clubs = Club.query.order_by(Club.name.asc())
    return render_template("admin/clubs.html", clubs=clubs)


@admin_bp.route("/clubs/<int:club_id>/members")
@admin_required
def club_members(club_id):
    club = db.session.get(Club, club_id)
    if not club:
        abort(404)
    members = club.memberships.filter_by(is_active=True).all()
    return render_template("admin/club_members.html", club=club, members=members)
