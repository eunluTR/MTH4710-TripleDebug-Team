from datetime import datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for, abort
from flask_login import current_user, login_user, logout_user
from werkzeug.security import check_password_hash

from ..extensions import db
from ..forms.auth import ManagerLoginForm
from ..forms.manager import (
    ClubProfileForm,
    MembershipDecisionForm,
    AnnouncementForm,
    EventProposalForm,
)
from ..models import (
    ClubManager,
    MembershipApplication,
    MembershipApplicationStatus,
    Membership,
    Announcement,
    Event,
    EventStatus,
    NotificationType,
    EventRegistration,
)
from ..rbac import manager_required
from ..utils import create_notification


manager_bp = Blueprint("manager", __name__)

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


def _manager_club():
    return getattr(current_user, "club", None)


@manager_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated and hasattr(current_user, "club_id"):
        return redirect(url_for("manager.dashboard"))
    form = ManagerLoginForm()
    ip_address = request.remote_addr or "unknown"
    if form.validate_on_submit():
        if _rate_limited(ip_address):
            flash("Too many login attempts. Try again later.", "error")
            return render_template("manager/login.html", form=form)
        manager = ClubManager.query.filter_by(email=form.email.data.lower()).first()
        if manager and manager.is_active and check_password_hash(manager.password_hash, form.password.data):
            login_user(manager)
            return redirect(url_for("manager.dashboard"))
        _record_attempt(ip_address)
        flash("Invalid credentials.", "error")
    return render_template("manager/login.html", form=form)


@manager_bp.route("/logout")
@manager_required
def logout():
    logout_user()
    flash("Logged out.", "info")
    return redirect(url_for("manager.login"))


@manager_bp.route("/dashboard")
@manager_required
def dashboard():
    club = _manager_club()
    if not club:
        abort(403)
    pending_memberships = MembershipApplication.query.filter_by(
        club_id=club.id, status=MembershipApplicationStatus.PENDING
    ).count()
    pending_events = Event.query.filter_by(
        club_id=club.id, status=EventStatus.PENDING_APPROVAL
    ).count()
    upcoming_events = (
        Event.query.filter(
            Event.club_id == club.id,
            Event.status == EventStatus.APPROVED,
            Event.start_datetime >= datetime.utcnow(),
        )
        .order_by(Event.start_datetime.asc())
        .limit(5)
        .all()
    )
    return render_template(
        "manager/dashboard.html",
        club=club,
        pending_memberships=pending_memberships,
        pending_events=pending_events,
        upcoming_events=upcoming_events,
    )


@manager_bp.route("/club/profile", methods=["GET", "POST"])
@manager_required
def club_profile():
    club = _manager_club()
    if not club:
        abort(403)
    form = ClubProfileForm(obj=club)
    if form.validate_on_submit():
        club.name = form.name.data
        club.description = form.description.data
        club.category = form.category.data
        club.logo_url = form.logo_url.data
        club.contact_email = form.contact_email.data
        db.session.commit()
        flash("Club profile updated.", "success")
        return redirect(url_for("manager.club_profile"))
    return render_template("manager/club_profile.html", form=form, club=club)


@manager_bp.route("/memberships/applications")
@manager_required
def membership_applications():
    club = _manager_club()
    if not club:
        abort(403)
    pending = MembershipApplication.query.filter_by(
        club_id=club.id, status=MembershipApplicationStatus.PENDING
    ).order_by(MembershipApplication.created_at.desc())
    history = MembershipApplication.query.filter(
        MembershipApplication.club_id == club.id,
        MembershipApplication.status != MembershipApplicationStatus.PENDING,
    ).order_by(MembershipApplication.decided_at.desc())
    form = MembershipDecisionForm()
    return render_template(
        "manager/membership_applications.html",
        pending=pending,
        history=history,
        form=form,
    )


@manager_bp.route("/memberships/applications/<int:application_id>/decide", methods=["POST"])
@manager_required
def decide_membership(application_id):
    club = _manager_club()
    if not club:
        abort(403)
    application = MembershipApplication.query.filter_by(
        id=application_id, club_id=club.id
    ).first_or_404()
    form = MembershipDecisionForm()
    if form.validate_on_submit():
        if application.status != MembershipApplicationStatus.PENDING:
            flash("Application already decided.", "info")
            return redirect(url_for("manager.membership_applications"))
        application.decided_at = datetime.utcnow()
        application.decided_by_manager_id = current_user.id
        application.decision_reason = form.decision_reason.data
        if form.decision.data == "approve":
            application.status = MembershipApplicationStatus.APPROVED
            membership = Membership.query.filter_by(
                club_id=club.id, user_id=application.user_id
            ).first()
            if membership:
                membership.is_active = True
            else:
                membership = Membership(club_id=club.id, user_id=application.user_id)
                db.session.add(membership)
            create_notification(
                application.user_id,
                NotificationType.MEMBERSHIP_DECISION,
                "Membership Approved",
                f"Your membership application to {club.name} was approved.",
                related_object_type="MembershipApplication",
                related_object_id=application.id,
            )
        else:
            application.status = MembershipApplicationStatus.REJECTED
            create_notification(
                application.user_id,
                NotificationType.MEMBERSHIP_DECISION,
                "Membership Rejected",
                f"Your membership application to {club.name} was rejected.",
                related_object_type="MembershipApplication",
                related_object_id=application.id,
            )
        db.session.commit()
        flash("Decision saved.", "success")
    else:
        flash("Unable to process decision.", "error")
    return redirect(url_for("manager.membership_applications"))


@manager_bp.route("/announcements")
@manager_required
def announcements():
    club = _manager_club()
    if not club:
        abort(403)
    items = Announcement.query.filter_by(club_id=club.id).order_by(Announcement.created_at.desc())
    return render_template("manager/announcements.html", announcements=items)


@manager_bp.route("/announcements/new", methods=["GET", "POST"])
@manager_required
def new_announcement():
    club = _manager_club()
    if not club:
        abort(403)
    form = AnnouncementForm()
    if form.validate_on_submit():
        announcement = Announcement(
            club_id=club.id,
            title=form.title.data,
            body=form.body.data,
            created_by_manager_id=current_user.id,
        )
        db.session.add(announcement)
        db.session.flush()
        members = Membership.query.filter_by(club_id=club.id, is_active=True).all()
        for member in members:
            create_notification(
                member.user_id,
                NotificationType.ANNOUNCEMENT,
                f"{club.name} Announcement",
                announcement.title,
                related_object_type="Announcement",
                related_object_id=announcement.id,
            )
        db.session.commit()
        flash("Announcement posted.", "success")
        return redirect(url_for("manager.announcements"))
    return render_template("manager/announcement_new.html", form=form)


@manager_bp.route("/events")
@manager_required
def events():
    club = _manager_club()
    if not club:
        abort(403)
    events = Event.query.filter_by(club_id=club.id).order_by(Event.start_datetime.desc())
    return render_template("manager/events.html", events=events)


@manager_bp.route("/events/new", methods=["GET", "POST"])
@manager_required
def new_event():
    club = _manager_club()
    if not club:
        abort(403)
    form = EventProposalForm()
    if form.validate_on_submit():
        event = Event(
            club_id=club.id,
            title=form.title.data,
            description=form.description.data,
            location=form.location.data,
            start_datetime=form.start_datetime.data,
            end_datetime=form.end_datetime.data,
            capacity=form.capacity.data,
            registration_deadline=form.registration_deadline.data,
            status=EventStatus.PENDING_APPROVAL,
            created_by_manager_id=current_user.id,
        )
        db.session.add(event)
        db.session.commit()
        flash("Event proposal submitted.", "success")
        return redirect(url_for("manager.events"))
    return render_template("manager/event_new.html", form=form)


@manager_bp.route("/events/<int:event_id>/registrations")
@manager_required
def event_registrations(event_id):
    club = _manager_club()
    if not club:
        abort(403)
    event = Event.query.filter_by(id=event_id, club_id=club.id).first_or_404()
    registrations = EventRegistration.query.filter_by(event_id=event.id).order_by(
        EventRegistration.registered_at.desc()
    )
    return render_template(
        "manager/event_registrations.html", event=event, registrations=registrations
    )
