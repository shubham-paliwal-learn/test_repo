"""Small helpers shared by all API blueprints: responses, validation, pagination."""
from datetime import date, datetime

from flask import jsonify, request

from app.extensions import db


class ValidationError(Exception):
    def __init__(self, message: str, status: int = 400, fields: dict | None = None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.fields = fields or {}


def success_response(data=None, message: str = "OK", status: int = 200, extra: dict | None = None):
    payload = {"success": True, "message": message, "data": data}
    if extra:
        payload.update(extra)
    return jsonify(payload), status


def error_response(message: str, status: int = 400, fields: dict | None = None):
    payload = {"success": False, "message": message, "errors": fields or {}}
    return jsonify(payload), status


def parse_date(value, field: str, required: bool = False) -> date | None:
    if value in (None, ""):
        if required:
            raise ValidationError(f"{field} is required.")
        return None
    if isinstance(value, (datetime,)):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError:
        raise ValidationError(f"{field} must be a valid date in YYYY-MM-DD format.")


def to_int(value, field: str, minimum: int | None = None, maximum: int | None = None,
           required: bool = False) -> int | None:
    if value in (None, ""):
        if required:
            raise ValidationError(f"{field} is required.")
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{field} must be an integer.")
    if minimum is not None and number < minimum:
        raise ValidationError(f"{field} must be at least {minimum}.")
    if maximum is not None and number > maximum:
        raise ValidationError(f"{field} must be at most {maximum}.")
    return number


def to_float(value, field: str, minimum: float | None = None) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{field} must be a number.")
    if minimum is not None and number < minimum:
        raise ValidationError(f"{field} cannot be less than {minimum}.")
    return number


def require(payload: dict, *fields: str) -> dict:
    missing = [f for f in fields if payload.get(f) in (None, "")]
    if missing:
        raise ValidationError("Missing required field(s): " + ", ".join(missing),
                              fields={f: "This field is required." for f in missing})
    return payload


def clean_string(value, field: str, min_length: int = 1, max_length: int = 200,
                 required: bool = True) -> str | None:
    if value is None:
        value = ""
    text = str(value).strip()
    if required and not text:
        raise ValidationError(f"{field} is required.")
    if text and (len(text) < min_length or len(text) > max_length):
        raise ValidationError(f"{field} must be between {min_length} and {max_length} characters.")
    return text or None


EMAIL_CHARS = ("@", ".")


def valid_email(value: str, field: str = "Email") -> str:
    email = clean_string(value, field, min_length=5, max_length=120)
    if email and (EMAIL_CHARS[0] not in email or email.count(".") == 0 or email.startswith(".")
                  or email.endswith("@")):
        raise ValidationError("Please provide a valid email address.", fields={field.lower(): "Invalid email"})
    return email


def get_json(request_obj=request) -> dict:
    payload = request_obj.get_json(silent=True)
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise ValidationError("Request body must be a JSON object.")
    return payload


def paginate(query, serializer, default_per_page: int = 10, max_per_page: int = 100):
    try:
        page = max(int(request.args.get("page", 1)), 1)
    except ValueError:
        page = 1
    try:
        per_page = min(max(int(request.args.get("per_page", default_per_page)), 1), max_per_page)
    except ValueError:
        per_page = default_per_page
    items, total = _paginate_query(query, page, per_page)
    return {
        "items": [serializer(item) for item in items],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": max((total + per_page - 1) // per_page, 1),
        },
    }


def _paginate_query(query, page: int, per_page: int):
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return items, total


def commit():
    try:
        db.session.commit()
    except Exception as exc:  # pragma: no cover
        db.session.rollback()
        raise ValidationError(f"Database error: {exc}")
