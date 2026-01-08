from functools import wraps

from flask import abort
from flask_login import current_user, login_required

from .models import User, UserRole, ClubManager


def is_manager_user():
    return isinstance(current_user._get_current_object(), ClubManager)


def roles_required(*roles):
    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapper(*args, **kwargs):
            if is_manager_user():
                abort(403)
            if not isinstance(current_user._get_current_object(), User):
                abort(403)
            if current_user.role not in roles:
                abort(403)
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def admin_required(fn):
    return roles_required(UserRole.SKS_ADMIN)(fn)


def student_required(fn):
    return roles_required(UserRole.STUDENT)(fn)


def manager_required(fn):
    @wraps(fn)
    @login_required
    def wrapper(*args, **kwargs):
        if not is_manager_user():
            abort(403)
        return fn(*args, **kwargs)

    return wrapper
