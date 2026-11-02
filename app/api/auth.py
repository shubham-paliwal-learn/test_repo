"""Authentication endpoints (login for all roles, self-registration for trekkers only)."""
from flask import Blueprint, current_app, request

from app.api.helpers import (
    ValidationError,
    clean_string,
    commit,
    error_response,
    get_json,
    success_response,
    valid_email,
)
from app.extensions import db
from app.models import (
    ROLE_ADMIN,
    ROLE_STAFF,
    ROLE_USER,
    USER_ACTIVE,
    User,
)
from app.services.auth import generate_token, get_current_user, login_required
from app.services.cache_service import cache

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

MIN_PASSWORD_LENGTH = 8


def _validate_password(password: str) -> str:
    password = password or ""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValidationError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters.",
            fields={"password": f"Minimum {MIN_PASSWORD_LENGTH} characters required."},
        )
    return password


@auth_bp.post("/register")
def register():
    """Self-registration is allowed only for Users (Trekkers)."""
    payload = get_json()
    full_name = clean_string(payload.get("full_name"), "Full name", min_length=3, max_length=120)
    username = (clean_string(payload.get("username"), "Username", min_length=3, max_length=64) or "").lower()
    email = valid_email(payload.get("email"))
    phone = clean_string(payload.get("phone"), "Phone", min_length=8, max_length=20, required=False)
    password = _validate_password(str(payload.get("password") or ""))
    confirm = str(payload.get("confirm_password") or password)

    if payload.get("role") in (ROLE_ADMIN, ROLE_STAFF):
        return error_response("Admin and Staff accounts cannot self-register. Contact the administrator.", 403)
    if not username.replace("_", "").replace(".", "").isalnum():
        raise ValidationError("Username may only contain letters, numbers, dot and underscore.",
                              fields={"username": "Invalid characters"})
    if password != confirm:
        raise ValidationError("Passwords do not match.", fields={"confirm_password": "Passwords do not match"})

    if User.query.filter(db.func.lower(User.username) == username).first():
        raise ValidationError("Username already taken.", fields={"username": "Already registered"})
    if User.query.filter(db.func.lower(User.email) == email.lower()).first():
        raise ValidationError("Email already registered.", fields={"email": "Already registered"})

    user = User(
        username=username,
        email=email.lower(),
        full_name=full_name,
        phone=phone,
        role=ROLE_USER,
        status=USER_ACTIVE,
    )
    user.set_password(password)
    db.session.add(user)
    commit()
    cache.invalidate_prefix("treks")
    return success_response(generate_token(user), "Registration successful", 201)


@auth_bp.post("/login")
def login():
    """Unified login for Admin / Staff / Trekker (session token = JWT)."""
    payload = get_json()
    identifier = clean_string(payload.get("username") or payload.get("email"), "Username or email", required=True)
    password = str(payload.get("password") or "")
    requested_role = (payload.get("role") or "").strip().lower()

    if not identifier or not password:
        return error_response("Username/email and password are required.", 400)

    bucket = f"login:{identifier.lower()}:{request.remote_addr}"
    if not cache.rate_limited(bucket, limit=8, window_seconds=60):
        return error_response("Too many login attempts. Please try again in a minute.", 429)

    user = User.query.filter(
        db.or_(db.func.lower(User.username) == identifier.lower(),
               db.func.lower(User.email) == identifier.lower())
    ).first()

    if user is None or not user.check_password(password):
        return error_response("Invalid credentials. Please check your username and password.", 401)
    if user.status != USER_ACTIVE:
        return error_response(f"Your account is {user.status.lower()}. Please contact the administrator.", 403)
    if requested_role and requested_role != user.role:
        return error_response(
            f"This account is registered as '{user.role}'. Please use the {user.role} login option.", 403
        )

    return success_response(generate_token(user), f"Welcome back, {user.full_name}!")


@auth_bp.get("/me")
@login_required
def me():
    from flask import g

    return success_response(g.current_user.to_dict(include_private=True), "Profile loaded")


@auth_bp.put("/profile")
@login_required
def update_profile():
    """Users can update their own profile; admin/staff may also edit contact info."""
    from flask import g

    user = g.current_user
    payload = get_json()

    full_name = clean_string(payload.get("full_name"), "Full name", min_length=3, max_length=120,
                            required="full_name" in payload)
    if full_name:
        user.full_name = full_name

    phone = clean_string(payload.get("phone"), "Phone", min_length=8, max_length=20, required=False)
    if payload.get("phone") is not None:
        user.phone = phone

    if "email" in payload and payload["email"]:
        email = valid_email(payload.get("email"))
        clash = User.query.filter(db.func.lower(User.email) == email.lower(), User.id != user.id).first()
        if clash:
            raise ValidationError("Email already in use.", fields={"email": "Already registered"})
        user.email = email.lower()

    if user.role == ROLE_STAFF:
        if "specialization" in payload:
            user.specialization = clean_string(payload.get("specialization"), "Specialization",
                                               min_length=2, max_length=80, required=False)
        if "contact_details" in payload:
            user.contact_details = clean_string(payload.get("contact_details"), "Contact details",
                                                min_length=2, max_length=200, required=False)

    new_password = str(payload.get("password") or "")
    if new_password:
        old_password = str(payload.get("current_password") or "")
        if not user.check_password(old_password):
            raise ValidationError("Current password is incorrect.",
                                  fields={"current_password": "Incorrect password"})
        _validate_password(new_password)
        user.set_password(new_password)

    commit()
    cache.invalidate_prefix("users")
    return success_response(user.to_dict(include_private=True), "Profile updated successfully")


@auth_bp.post("/logout")
@login_required
def logout():
    """Stateless JWT: client discards the token. Endpoint kept for symmetry/audit."""
    return success_response(None, "Logged out successfully")


@auth_bp.get("/health")
def health():
    return success_response(
        {
            "status": "ok",
            "cache_backend": cache.backend,
            "roles": [ROLE_USER, ROLE_STAFF, ROLE_ADMIN],
        },
        "TMA API is up",
    )
