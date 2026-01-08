from datetime import datetime

from flask import request

from .extensions import db
from .models import Notification, NotificationType, AuditLog, AuditActorType


def create_notification(user_id, ntype, title, body, related_object_type=None, related_object_id=None):
    note = Notification(
        user_id=user_id,
        type=ntype,
        title=title,
        body=body,
        related_object_type=related_object_type,
        related_object_id=related_object_id,
    )
    db.session.add(note)
    return note


def log_audit(actor_type, actor_id, action, object_type, object_id, details=None):
    entry = AuditLog(
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        object_type=object_type,
        object_id=object_id,
        details=details,
        created_at=datetime.utcnow(),
    )
    db.session.add(entry)
    return entry


def get_page(default=1):
    try:
        return int(request.args.get("page", default))
    except (TypeError, ValueError):
        return default
