"""Trek resources: listing/search (Redis cached), admin CRUD, staff slot & status management."""
from flask import Blueprint, current_app, g, request

from app.api.helpers import (
    ValidationError,
    clean_string,
    commit,
    get_json,
    paginate,
    parse_date,
    success_response,
    to_float,
    to_int,
)
from app.extensions import db
from app.models import (
    BOOKING_BOOKED,
    DIFFICULTIES,
    ROLE_STAFF,
    ROLE_USER,
    TREK_APPROVED,
    TREK_CLOSED,
    TREK_COMPLETED,
    TREK_OPEN,
    TREK_PENDING,
    TREK_STATUSES,
    Booking,
    Notification,
    StaffAssignment,
    Trek,
    User,
)
from app.services.auth import admin_or_staff_required, admin_required, login_required, staff_required
from app.services.cache_service import cache

treks_bp = Blueprint("treks", __name__, url_prefix="/api/treks")

CACHE_LIST_PREFIX = "treks:list"
CACHE_DETAIL_PREFIX = "treks:detail"


# --------------------------------------------------------------------- helpers
def _ttl() -> int:
    return int(current_app.config.get("CACHE_TTL_SECONDS", 60))


def _invalidate_trek_cache(trek_id: int | None = None) -> None:
    cache.invalidate_prefix(CACHE_LIST_PREFIX)
    cache.delete_keys("treks:filters")
    if trek_id is not None:
        cache.delete_keys(f"{CACHE_DETAIL_PREFIX}:{trek_id}")


def _truthy(name: str) -> bool:
    return (request.args.get(name) or "").strip().lower() in ("1", "true", "yes")


def _apply_filters(query):
    search = (request.args.get("search") or "").strip()
    difficulty = (request.args.get("difficulty") or "").strip().title()
    location = (request.args.get("location") or "").strip()
    status = (request.args.get("status") or "").strip().title()
    min_duration = to_int(request.args.get("min_duration"), "min_duration", minimum=1)
    max_duration = to_int(request.args.get("max_duration"), "max_duration", minimum=1)
    staff_id = to_int(request.args.get("staff_id"), "staff_id", minimum=1)

    if search:
        like = f"%{search.lower()}%"
        query = query.filter(
            db.or_(
                db.func.lower(Trek.name).like(like),
                db.func.lower(Trek.location).like(like),
                db.func.lower(db.coalesce(Trek.region, "")).like(like),
                db.func.lower(db.coalesce(Trek.description, "")).like(like),
            )
        )
    if difficulty and difficulty in DIFFICULTIES:
        query = query.filter(Trek.difficulty == difficulty)
    if location:
        query = query.filter(db.func.lower(Trek.location).like(f"%{location.lower()}%"))
    if status and status in TREK_STATUSES:
        query = query.filter(Trek.status == status)
    if min_duration:
        query = query.filter(Trek.duration_days >= min_duration)
    if max_duration:
        query = query.filter(Trek.duration_days <= max_duration)
    if staff_id:
        query = query.filter(Trek.assigned_staff_id == staff_id)
    if _truthy("only_available"):
        query = query.filter(Trek.available_slots > 0)
    if _truthy("upcoming"):
        query = query.filter(Trek.start_date >= db.func.date("now"))

    allowed = {
        "start_date": Trek.start_date,
        "name": Trek.name,
        "difficulty": Trek.difficulty,
        "duration_days": Trek.duration_days,
        "available_slots": Trek.available_slots,
        "base_price": Trek.base_price,
        "created_at": Trek.created_at,
    }
    column = allowed.get(request.args.get("sort_by", "start_date"), Trek.start_date)
    descending = (request.args.get("order", "asc")).lower() == "desc"
    order = db.desc(column) if descending else db.asc(column)
    return query.order_by(order, Trek.id)


class NotFoundError(Exception):
    def __init__(self, message: str, status: int = 404):
        super().__init__(message)
        self.message = message
        self.status = status


def _get_trek_or_404(trek_id: int) -> Trek:
    trek = db.session.get(Trek, trek_id)
    if trek is None:
        raise NotFoundError("Trek not found.")
    return trek


def _is_manageable(trek: Trek, user: User) -> bool:
    if user.role == "admin":
        return True
    if trek.assigned_staff_id == user.id:
        return True
    return bool(db.session.query(StaffAssignment).filter_by(trek_id=trek.id, staff_id=user.id).first())


def _ensure_manageable(trek: Trek) -> None:
    """Only the assigned staff (lead or support) may manage a trek."""
    user = g.current_user
    if not _is_manageable(trek, user):
        raise ValidationError("You are not assigned to manage this trek.", status=403)


# ------------------------------------------------------------------ read APIs
@treks_bp.get("/")
@login_required
def list_treks():
    """List treks with search/filter/sort. Trekkers only see bookable treks. Redis cached."""
    user = g.current_user

    if user.role == ROLE_STAFF:
        base = Trek.query.filter(
            db.or_(
                Trek.assigned_staff_id == user.id,
                Trek.id.in_(db.session.query(StaffAssignment.trek_id).filter_by(staff_id=user.id)),
            )
        )
    elif user.role == ROLE_USER and not _truthy("all"):
        base = Trek.query.filter(Trek.status.in_([TREK_OPEN, TREK_APPROVED]))
    else:
        base = Trek.query

    query = _apply_filters(base)
    key = (
        f"{CACHE_LIST_PREFIX}:{user.role}:{user.id if user.role == ROLE_USER else 0}"
        f":{request.query_string.decode('utf-8')}"
    )

    data = cache.memoize(
        key,
        lambda: paginate(query, lambda t: t.to_dict()),
        ttl=_ttl(),
        force_refresh=_truthy("refresh"),
    )
    payload = dict(data)
    payload["cache_backend"] = cache.backend
    return success_response(payload, "Treks loaded")


@treks_bp.get("/filters")
@login_required
def trek_filter_options():
    """Distinct filter values + difficulty distribution used by the UI."""

    def producer():
        locations = [r[0] for r in db.session.query(Trek.location).distinct().order_by(Trek.location).all()]
        durations = [
            r[0] for r in db.session.query(Trek.duration_days).distinct().order_by(Trek.duration_days).all()
        ]
        return {
            "difficulties": list(DIFFICULTIES),
            "statuses": list(TREK_STATUSES),
            "locations": locations,
            "durations": durations,
            "difficulty_counts": {d: Trek.query.filter_by(difficulty=d).count() for d in DIFFICULTIES},
        }

    return success_response(cache.memoize("treks:filters", producer, ttl=_ttl()), "Filters loaded")


@treks_bp.get("/<int:trek_id>")
@login_required
def get_trek(trek_id: int):
    """Single trek detail (cached). Participants included for admin/assigned staff."""
    trek = _get_trek_or_404(trek_id)
    user = g.current_user
    if user.role == ROLE_USER and trek.status not in (TREK_OPEN, TREK_APPROVED):
        raise NotFoundError("Trek is not available.")

    payload = dict(
        cache.memoize(f"{CACHE_DETAIL_PREFIX}:{trek_id}", lambda: trek.to_dict(), ttl=_ttl(),
                      force_refresh=_truthy("refresh"))
    )
    if user.role in ("admin", "staff") and _is_manageable(trek, user):
        participants = (
            Booking.query.filter_by(trek_id=trek_id, status=BOOKING_BOOKED)
            .order_by(Booking.booking_date)
            .all()
        )
        payload["participants"] = [b.user.to_dict() for b in participants]
    my_booking = Booking.query.filter_by(user_id=user.id, trek_id=trek_id).first() if user.role == ROLE_USER else None
    payload["my_booking_status"] = my_booking.status if my_booking else None
    payload["can_manage"] = _is_manageable(trek, user)
    return success_response(payload, "Trek loaded")


@treks_bp.get("/<int:trek_id>/participants")
@admin_or_staff_required
def trek_participants(trek_id: int):
    trek = _get_trek_or_404(trek_id)
    if g.current_user.role == ROLE_STAFF:
        _ensure_manageable(trek)
    query = Booking.query.filter_by(trek_id=trek_id).order_by(Booking.booking_date.desc())
    status = (request.args.get("status") or "").strip().title()
    if status:
        query = query.filter(Booking.status == status)
    return success_response(paginate(query, lambda b: b.to_dict()), "Participants loaded")


# ------------------------------------------------------------- validation
def _validate_trek_payload(payload: dict, partial: bool = False) -> dict:
    fields: dict = {}

    name = clean_string(payload.get("name"), "Trek name", min_length=4, max_length=120, required=not partial)
    if name or not partial:
        fields["name"] = name

    location = clean_string(payload.get("location"), "Location", min_length=3, max_length=120,
                            required=not partial)
    if location or not partial:
        fields["location"] = location

    if "region" in payload:
        fields["region"] = clean_string(payload.get("region"), "Region", min_length=2, max_length=80,
                                        required=False)

    if "difficulty" in payload or not partial:
        difficulty = (clean_string(payload.get("difficulty"), "Difficulty", min_length=4, max_length=12,
                                   required=not partial) or "").title()
        if difficulty not in DIFFICULTIES:
            raise ValidationError("Difficulty must be one of Easy / Moderate / Hard.",
                                  fields={"difficulty": "Invalid value"})
        fields["difficulty"] = difficulty

    duration = to_int(payload.get("duration_days"), "Duration (days)", minimum=1, maximum=90,
                      required=not partial)
    if duration is not None:
        fields["duration_days"] = duration

    slots = to_int(payload.get("total_slots"), "Total slots", minimum=1, maximum=500, required=not partial)
    if slots is not None:
        fields["total_slots"] = slots

    start_date = parse_date(payload.get("start_date"), "Start date", required=not partial)
    if start_date:
        fields["start_date"] = start_date
    end_date = parse_date(payload.get("end_date"), "End date")
    if end_date:
        fields["end_date"] = end_date

    final_start, final_end = fields.get("start_date"), fields.get("end_date")
    if final_start and final_end and final_end < final_start:
        raise ValidationError("End date cannot be before the start date.",
                              fields={"end_date": "Must be on or after the start date"})
    if final_start and final_end and fields.get("duration_days"):
        span = (final_end - final_start).days + 1
        if span != fields["duration_days"]:
            raise ValidationError(
                f"Duration ({fields['duration_days']} day(s)) does not match the selected date range "
                f"({span} day(s)).",
                fields={"duration_days": "Mismatch with start/end dates"},
            )

    if "base_price" in payload:
        fields["base_price"] = to_float(payload.get("base_price"), "Base price", minimum=0) or 0.0
    if "min_age" in payload:
        fields["min_age"] = to_int(payload.get("min_age"), "Minimum age", minimum=5, maximum=100) or 10
    if "description" in payload:
        fields["description"] = clean_string(payload.get("description"), "Description", min_length=0,
                                             max_length=2000, required=False)
    if "instructions" in payload:
        fields["instructions"] = clean_string(payload.get("instructions"), "Instructions", min_length=0,
                                              max_length=2000, required=False)
    if "status" in payload:
        status = (clean_string(payload.get("status"), "Status", min_length=4, max_length=12,
                               required=False) or "").title()
        if status not in TREK_STATUSES:
            raise ValidationError("Invalid trek status.", fields={"status": "Invalid value"})
        fields["status"] = status
    if "assigned_staff_id" in payload:
        fields["assigned_staff_id"] = to_int(payload.get("assigned_staff_id"), "Assigned staff", minimum=1,
                                            required=False)
    return fields


def _assert_staff_exists(staff_id: int) -> User:
    staff = db.session.get(User, staff_id)
    if staff is None:
        raise ValidationError("Assigned staff member does not exist.",
                              fields={"assigned_staff_id": "Not found"})
    if staff.role != ROLE_STAFF:
        raise ValidationError("Only accounts with the staff role can be assigned to a trek.",
                              fields={"assigned_staff_id": "Must be a staff account"})
    return staff


# ------------------------------------------------------------- write APIs
@treks_bp.post("/")
@admin_required
def create_trek():
    payload = get_json()
    fields = _validate_trek_payload(payload)
    staff_id = fields.pop("assigned_staff_id", None)
    if staff_id:
        _assert_staff_exists(staff_id)

    trek = Trek(**fields)
    trek.assigned_staff_id = staff_id
    trek.created_by = g.current_user.id
    trek.status = fields.get("status") or TREK_PENDING
    trek.available_slots = trek.total_slots

    db.session.add(trek)
    db.session.flush()
    if staff_id:
        db.session.add(StaffAssignment(trek_id=trek.id, staff_id=staff_id, assigned_by=g.current_user.id,
                                       role_label="Lead"))
        trek.support_staff.append(db.session.get(User, staff_id))
    commit()
    _invalidate_trek_cache(trek.id)
    return success_response(trek.to_dict(), "Trek created successfully", 201)


@treks_bp.put("/<int:trek_id>")
@admin_or_staff_required
def update_trek(trek_id: int):
    """Admins edit everything; assigned staff may only change operational fields."""
    trek = _get_trek_or_404(trek_id)
    user = g.current_user
    payload = get_json()

    if user.role == ROLE_STAFF:
        _ensure_manageable(trek)
        allowed_for_staff = {"total_slots", "available_slots", "start_date", "end_date",
                             "duration_days", "instructions"}
        forbidden = sorted(k for k in payload if k not in allowed_for_staff)
        if forbidden:
            raise ValidationError("Staff members cannot modify: " + ", ".join(forbidden) + ".", status=403)

    fields = _validate_trek_payload(payload, partial=True)
    staff_id = fields.pop("assigned_staff_id", None)

    booked = trek.booked_count
    new_total = fields.get("total_slots")
    if new_total is not None and new_total < booked:
        raise ValidationError(f"Total slots cannot be lower than existing bookings ({booked}).",
                              fields={"total_slots": f"Minimum {booked}"})

    if staff_id:
        assigned = _assert_staff_exists(staff_id)
        if trek.assigned_staff_id != staff_id:
            if not StaffAssignment.query.filter_by(trek_id=trek.id, staff_id=staff_id).first():
                db.session.add(StaffAssignment(trek_id=trek.id, staff_id=staff_id, assigned_by=user.id,
                                               role_label="Lead"))
            if assigned not in trek.support_staff:
                trek.support_staff.append(assigned)
            trek.assigned_staff_id = staff_id

    for attr, value in fields.items():
        setattr(trek, attr, value)

    if new_total is not None:
        trek.available_slots = max(new_total - booked, 0)

    commit()
    _invalidate_trek_cache(trek.id)
    return success_response(trek.to_dict(), "Trek updated successfully")


@treks_bp.delete("/<int:trek_id>")
@admin_required
def delete_trek(trek_id: int):
    trek = _get_trek_or_404(trek_id)
    active_bookings = trek.bookings.filter_by(status=BOOKING_BOOKED).count()
    if active_bookings:
        raise ValidationError(
            f"Trek has {active_bookings} active booking(s). Close it or cancel the bookings first.",
            status=409,
        )
    db.session.delete(trek)
    commit()
    _invalidate_trek_cache(trek_id)
    return success_response(None, "Trek removed successfully")


@treks_bp.patch("/<int:trek_id>/slots")
@admin_or_staff_required
def update_slots(trek_id: int):
    trek = _get_trek_or_404(trek_id)
    if g.current_user.role == ROLE_STAFF:
        _ensure_manageable(trek)

    payload = get_json()
    total = to_int(payload.get("total_slots"), "Total slots", minimum=1, maximum=500, required=True)
    booked = trek.booked_count
    if total < booked:
        raise ValidationError(f"Total slots cannot be lower than confirmed bookings ({booked}).",
                              fields={"total_slots": f"Minimum {booked}"})
    trek.total_slots = total
    trek.available_slots = total - booked
    commit()
    _invalidate_trek_cache(trek_id)
    return success_response(trek.to_dict(), "Slots updated successfully")


@treks_bp.patch("/<int:trek_id>/status")
@admin_or_staff_required
def update_status(trek_id: int):
    """Staff: Open / Closed / Completed. Admin: any status (incl. Pending/Approved)."""
    trek = _get_trek_or_404(trek_id)
    user = g.current_user
    payload = get_json()

    new_status = (clean_string(payload.get("status"), "Status", min_length=4, max_length=12,
                               required=True) or "").title()
    if new_status not in TREK_STATUSES:
        raise ValidationError("Invalid trek status.", fields={"status": "Invalid value"})

    if user.role == ROLE_STAFF:
        _ensure_manageable(trek)
        staff_allowed = {TREK_OPEN, TREK_CLOSED, TREK_COMPLETED}
        if new_status not in staff_allowed:
            raise ValidationError("Staff can only set the status to Open, Closed or Completed.", status=403)
        if new_status == TREK_OPEN and trek.status not in (TREK_APPROVED, TREK_CLOSED):
            raise ValidationError("The trek must be Approved by the admin before opening bookings.")
        if new_status == TREK_COMPLETED and trek.status not in (TREK_OPEN, TREK_CLOSED):
            raise ValidationError("Only an Open or Closed trek can be marked as Completed.")

    if new_status == TREK_OPEN and trek.assigned_staff_id is None:
        raise ValidationError("Assign a staff member before opening the trek for bookings.")

    previous_status = trek.status
    trek.status = new_status
    if new_status == TREK_COMPLETED:
        for booking in trek.bookings.filter_by(status=BOOKING_BOOKED).all():
            booking.status = "Completed"
    commit()
    _invalidate_trek_cache(trek_id)

    if new_status == TREK_COMPLETED and previous_status != TREK_COMPLETED:
        _notify_participants(
            trek,
            "Trek completed",
            f"Your trek '{trek.name}' has been marked as completed. Thanks for trekking with us!",
        )
    return success_response(trek.to_dict(), f"Trek status set to {new_status}")


def _notify_participants(trek: Trek, title: str, message: str) -> None:
    for booking in trek.bookings.filter_by(status="Booked").all():
        db.session.add(Notification(user_id=booking.user_id, title=title, message=message, category="trek"))
    db.session.commit()


@treks_bp.post("/<int:trek_id>/staff")
@admin_required
def assign_staff(trek_id: int):
    trek = _get_trek_or_404(trek_id)
    payload = get_json()
    staff_id = to_int(payload.get("staff_id"), "Staff", minimum=1, required=True)
    staff = _assert_staff_exists(staff_id)
    role_label = clean_string(payload.get("role_label"), "Role label", min_length=2, max_length=40,
                              required=False) or "Support"

    if StaffAssignment.query.filter_by(trek_id=trek.id, staff_id=staff_id).first():
        raise ValidationError(f"{staff.full_name} is already assigned to this trek.")

    db.session.add(StaffAssignment(trek_id=trek.id, staff_id=staff_id, assigned_by=g.current_user.id,
                                   role_label=role_label))
    if trek.assigned_staff_id is None:
        trek.assigned_staff_id = staff_id
    if staff not in trek.support_staff:
        trek.support_staff.append(staff)
    commit()
    _invalidate_trek_cache(trek.id)
    return success_response(trek.to_dict(), f"{staff.full_name} assigned to {trek.name}")


@treks_bp.delete("/<int:trek_id>/staff/<int:staff_id>")
@admin_required
def unassign_staff(trek_id: int, staff_id: int):
    trek = _get_trek_or_404(trek_id)
    assignment = StaffAssignment.query.filter_by(trek_id=trek_id, staff_id=staff_id).first()
    if assignment is None:
        raise NotFoundError("Assignment not found.")
    db.session.delete(assignment)
    staff = db.session.get(User, staff_id)
    if staff is not None and staff in trek.support_staff:
        trek.support_staff.remove(staff)
    if trek.assigned_staff_id == staff_id:
        next_lead = StaffAssignment.query.filter(StaffAssignment.trek_id == trek_id,
                                                 StaffAssignment.staff_id != staff_id).first()
        trek.assigned_staff_id = next_lead.staff_id if next_lead else None
    commit()
    _invalidate_trek_cache(trek_id)
    return success_response(trek.to_dict(), "Staff unassigned from trek")
