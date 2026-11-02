"""JWT based authentication helpers and role-based access control decorators."""
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import current_app, g, request

from app.models import ROLE_ADMIN, ROLE_STAFF, ROLE_USER, User, USER_ACTIVE
from app.extensions import db


def _encode_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
        "name": user.full_name,
        "iat": now,
        "exp": now + timedelta(hours=current_app.config["JWT_EXPIRY_HOURS"]),
    }
    return jwt.encode(payload, current_app.config["JWT_SECRET_KEY"], algorithm=current_app.config["JWT_ALGORITHM"])


def generate_token(user: User) -> dict:
    return {
        "token": _encode_token(user),
        "token_type": "Bearer",
        "expires_in": int(current_app.config["JWT_EXPIRY_HOURS"] * 3600),
        "user": user.to_dict(),
    }


def decode_token(token: str) -> dict:
    return jwt.decode(token, current_app.config["JWT_SECRET_KEY"], algorithms=[current_app.config["JWT_ALGORITHM"]])


def get_current_user() -> User | None:
    """Resolve the authenticated user from the ``Authorization`` header (cached per request)."""
    if hasattr(g, "current_user"):
        return g.current_user

    header = request.headers.get("Authorization", "")
    token = None
    if header.lower().startswith("bearer "):
        token = header.split(" ", 1)[1].strip()
    elif header.strip():
        token = header.strip()

    g.current_user = None
    if not token:
        return None
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        g.auth_error = "Token has expired, please log in again."
        return None
    except jwt.PyJWTError:
        g.auth_error = "Invalid authentication token."
        return None

    user = db.session.get(User, int(payload.get("sub", 0)))
    if user is None:
        g.auth_error = "User account no longer exists."
        return None
    if user.status != USER_ACTIVE:
        g.auth_error = f"Account is {user.status.lower()}. Contact the administrator."
        return None
    g.current_user = user
    return user


def _unauthorized(message: str):
    from app.api.helpers import error_response

    return error_response(message, 401)


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if user is None:
            return _unauthorized(getattr(g, "auth_error", "Authentication required."))
        return view(*args, **kwargs)

    return wrapper


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            user = get_current_user()
            if user is None:
                return _unauthorized(getattr(g, "auth_error", "Authentication required."))
            if user.role not in roles:
                from app.api.helpers import error_response

                return error_response("You do not have permission to perform this action.", 403)
            return view(*args, **kwargs)

        return wrapper

    return decorator


admin_required = roles_required(ROLE_ADMIN)
staff_required = roles_required(ROLE_STAFF)
trekker_required = roles_required(ROLE_USER)
admin_or_staff_required = roles_required(ROLE_ADMIN, ROLE_STAFF)
