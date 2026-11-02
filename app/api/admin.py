"""Admin resources: dashboards, user/staff management, search, reports, jobs.

Everything in this blueprint is restricted to the Admin role (plus a couple of
read-only helpers used by staff dashboards which are explicitly guarded).
"""
from datetime import date, datetime, timedelta

from flask import Blueprint, g, request

from app.api.helpers import (
    NotFoundError,
    ValidationError,
    clean_string,
    commit,
    get_json,
    paginate,
    parse_date,
    success_response,
    to_int,
    valid_email,
)
from app.extensions import db
from app.models import (
    BOOKING_BOOKED,
    BOOKING_CANCELLED,
    BOOKING_COMPLETED,
    DIFFICULTIES,
    ROLE_ADMIN,
    ROLE_STAFF,
    ROLE_USER,
    ROLES,
    TREK_COMPLETED,
    TREK_OPEN,
    USER_ACTIVE,
    USER_BLACKLISTED,
    USER_DEACTIVATED,
    USER_STATUSES,
    Booking,
    JobRun,
    Notification,
    StaffAssignment,
    Trek,
    User,
)
from app.services.auth import admin_required, login_required
from app.services.cache_service import cache

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")

STATS_CACHE_KEY = "stats:dashboard"


def _ttl() -> int:
    from flask import current_app

    return int(current_app.config.get("CACHE_TTL_SECONDS", 60))


def _invalidate_stats() -> None:
    cache.invalidate_prefix("stats:")


# ------------------------------------------------------------------- dashboard
@admin_bp.get("/dashboard")
@admin_required
def dashboard():
    """Headline counters + charts for the admin dashboard (Redis cached)."""

    def producer():
        total_users = User.query.filter_by(role=ROLE_USER).count()
        total_staff = User.query.filter_by(role=ROLE_STAFF).count()
        total_treks = Trek.query.count()
        open_treks = Trek.query.filter_by(status=TREK_OPEN).count()
        total_bookings = Booking.query.count()
        active_bookings = Booking.query.filter_by(status=BOOKING_BOOKED).count()
        completed_bookings = Booking.query.filter_by(status=BOOKING_COMPLETED).count()
        cancelled_bookings = Booking.query.filter_by(status=BOOKING_CANCELLED).count()

        status_counts = {s: Trek.query.filter_by(status=s).count() for s in
                         ("Pending", "Approved", "Open", "Closed", "Completed")}
        difficulty_counts = {d: Trek.query.filter_by(difficulty=d).count() for d in DIFFICULTIES}

        popular_rows = (
            db.session.query(
                Trek.id, Trek.name, Trek.location, Trek.difficulty,
                db.func.count(Booking.id).label("bookings"),
                db.func.coalesce(db.func.sum(Booking.participants), 0).label("participants"),
            )
            .join(Booking, Booking.trek_id == Trek.id)
            .group_by(Trek.id, Trek.name, Trek.location, Trek.difficulty)
            .order_by(db.desc("bookings"))
            .limit(5)
            .all()
        )

        month_start = date.today().replace(day=1)
        bookings_this_month = Booking.query.filter(Booking.booking_date >= datetime.combine(month_start,
                                                                                             datetime.min.time())).count()
        revenue = db.session.query(db.func.coalesce(db.func.sum(Booking.amount), 0.0)).filter(
            Booking.status != BOOKING_CANCELLED
        ).scalar() or 0.0

        upcoming = (
            Trek.query.filter(Trek.start_date >= date.today())
            .order_by(Trek.start_date.asc())
            .limit(5)
            .all()
        )
        recent_bookings = Booking.query.order_by(Booking.booking_date.desc()).limit(5).all()

        return {
            "totals": {
                "treks": total_treks,
                "users": total_users,
                "staff": total_staff,
                "bookings": total_bookings,
                "open_treks": open_treks,
                "active_bookings": active_bookings,
                "completed_bookings": completed_bookings,
                "cancelled_bookings": cancelled_bookings,
                "bookings_this_month": bookings_this_month,
                "revenue": round(float(revenue), 2),
                "cache_backend": cache.backend,
            },
            "trek_status_counts": status_counts,
            "difficulty_counts": difficulty_counts,
            "popular_treks": [
                {
                    "id": row.id,
                    "name": row.name,
                    "location": row.location,
                    "difficulty": row.difficulty,
                    "bookings": row.bookings,
                    "participants": int(row.participants or 0),
                }
                for row in popular_rows
            ],
            "upcoming_treks": [t.to_dict(include_stats=False) for t in upcoming],
            "recent_bookings": [b.to_dict() for b in recent_bookings],
        }

    data = cache.memoize(STATS_CACHE_KEY, producer, ttl=_ttl(),
                         force_refresh=(request.args.get("refresh") or "").lower() in ("1", "true"))
    return success_response(data, "Dashboard loaded")


@admin_bp.get("/analytics")
@admin_required
def analytics():
    """Monthly participation series used by the ChartJS line/bar charts."""
    months = []
    today = date.today()
    cursor = today.replace(day=1)
    for _range in range(6):
        start = cursor
        end = (start.replace(day=28) + timedelta(days=7)).replace(day=1)
        months.append((start, end))
        cursor = end - timedelta(days=1)
    months.reverse()

    series = []
    for start, end in months:
        booking_rows = Booking.query.filter(Booking.booking_date >= datetime.combine(start, datetime.min.time()),
                                            Booking.booking_date < datetime.combine(end, datetime.min.time())).all()
        trek_rows = Trek.query.filter(Trek.start_date >= start, Trek.start_date < end).all()
        series.append({
            "month": start.strftime("%Y-%m"),
            "label": start.strftime("%b %Y"),
            "bookings": len(booking_rows),
            "participants": sum(b.participants for b in booking_rows if b.status != BOOKING_CANCELLED),
            "treks": len(trek_rows),
            "completed_treks": len([t for t in trek_rows if t.status == TREK_COMPLETED]),
            "revenue": round(sum(b.amount for b in booking_rows if b.status != BOOKING_CANCELLED), 2),
        })

    location_rows = (
        db.session.query(Trek.location, db.func.count(Booking.id))
        .join(Booking, Booking.trek_id == Trek.id)
        .group_by(Trek.location)
        .order_by(db.desc(db.func.count(Booking.id)))
        .limit(8)
        .all()
    )
    return success_response({
        "monthly": series,
        "by_location": [{"location": l, "bookings": c} for l, c in location_rows],
        "by_difficulty": {d: Trek.query.filter_by(difficulty=d).count() for d in DIFFICULTIES},
    }, "Analytics loaded")


# ------------------------------------------------------------- staff management
def _create_staff(payload: dict) -> User:
    full_name = clean_string(payload.get("full_name"), "Full name", min_length=3, max_length=120)
    username = (clean_string(payload.get("username"), "Username", min_length=3, max_length=64) or "").lower()
    email = valid_email(payload.get("email"))
    phone = clean_string(payload.get("phone"), "Phone", min_length=8, max_length=20, required=False)
    specialization = clean_string(payload.get("specialization"), "Specialization", min_length=2,
                                  max_length=80, required=False)
    contact_details = clean_string(payload.get("contact_details"), "Contact details", min_length=2,
                                   max_length=200, required=False)
    password = str(payload.get("password") or "")
    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters.",
                              fields={"password": "Minimum 8 characters required."})

    if not username.replace("_", "").replace(".", "").isalnum():
        raise ValidationError("Username may only contain letters, numbers, dot and underscore.",
                              fields={"username": "Invalid characters"})
    if User.query.filter(db.func.lower(User.username) == username).first():
        raise ValidationError("Username already taken.", fields={"username": "Already registered"})
    if User.query.filter(db.func.lower(User.email) == email.lower()).first():
        raise ValidationError("Email already registered.", fields={"email": "Already registered"})

    staff = User(
        username=username,
        email=email.lower(),
        full_name=full_name,
        phone=phone,
        role=ROLE_STAFF,
        status=USER_ACTIVE,
        specialization=specialization,
        contact_details=contact_details or phone,
    )
    staff.set_password(password)
    db.session.add(staff)
    commit()
    _invalidate_stats()
    cache.invalidate_prefix("users")
    return staff


@admin_bp.post("/staff")
@admin_required
def add_staff():
    """Admin creates Trek Staff accounts (staff cannot self-register)."""
    staff = _create_staff(get_json())
    return success_response(staff.to_dict(include_private=True), f"{staff.full_name} added as trek staff", 201)


@admin_bp.get("/staff")
@admin_required
def list_staff():
    query = User.query.filter_by(role=ROLE_STAFF)
    search = (request.args.get("search") or "").strip()
    status = (request.args.get("status") or "").strip().title()
    if search:
        like = f"%{search.lower()}%"
        query = query.filter(db.or_(db.func.lower(User.full_name).like(like),
                                    db.func.lower(User.username).like(like),
                                    db.func.lower(User.email).like(like)))
    if status and status in USER_STATUSES:
        query = query.filter(User.status == status)
    query = query.order_by(User.full_name.asc())

    page_data = paginate(query, lambda u: _staff_with_load(u))
    return success_response(page_data, "Staff list loaded")


def _staff_with_load(staff: User) -> dict:
    assigned = Trek.query.filter(Trek.assigned_staff_id == staff.id).count()
    support = db.session.query(StaffAssignment).filter_by(staff_id=staff.id).count()
    participants = (
        db.session.query(db.func.coalesce(db.func.sum(Booking.participants), 0))
        .join(Trek, Booking.trek_id == Trek.id)
        .filter(Trek.assigned_staff_id == staff.id, Booking.status == BOOKING_BOOKED)
        .scalar()
    )
    data = staff.to_dict(include_private=True)
    data.update({
        "assigned_treks": assigned,
        "support_assignments": support,
        "active_participants": int(participants or 0),
    })
    return data


@admin_bp.patch("/staff/<int:staff_id>/status")
@admin_required
def set_staff_status(staff_id: int):
    staff = db.session.get(User, staff_id)
    if staff is None or staff.role != ROLE_STAFF:
        raise NotFoundError("Staff member not found.")
    payload = get_json()
    new_status = (clean_string(payload.get("status"), "Status", min_length=6, max_length=12, required=True) or "").title()
    if new_status not in USER_STATUSES:
        raise ValidationError("Status must be Active, Deactivated or Blacklisted.",
                              fields={"status": "Invalid value"})
    staff.status = new_status
    reason = clean_string(payload.get("reason"), "Reason", min_length=2, max_length=200, required=False)
    if reason:
        staff.contact_details = f"{staff.contact_details or ''} | {new_status}: {reason}".strip(" |")
    db.session.add(Notification(
        user_id=staff.id,
        title=f"Account {new_status.lower()}",
        message=f"Your staff account has been set to {new_status}." + (f" Reason: {reason}" if reason else ""),
        category="account",
    ))
    commit()
    _invalidate_stats()
    return success_response(staff.to_dict(include_private=True), f"Staff marked as {new_status}")


@admin_bp.put("/staff/<int:staff_id>")
@admin_required
def update_staff(staff_id: int):
    staff = db.session.get(User, staff_id)
    if staff is None or staff.role != ROLE_STAFF:
        raise NotFoundError("Staff member not found.")
    payload = get_json()
    if "full_name" in payload:
        staff.full_name = clean_string(payload.get("full_name"), "Full name", min_length=3, max_length=120)
    if "phone" in payload:
        staff.phone = clean_string(payload.get("phone"), "Phone", min_length=8, max_length=20, required=False)
    if "specialization" in payload:
        staff.specialization = clean_string(payload.get("specialization"), "Specialization", min_length=2,
                                            max_length=80, required=False)
    if "contact_details" in payload:
        staff.contact_details = clean_string(payload.get("contact_details"), "Contact details", min_length=2,
                                             max_length=200, required=False)
    if "status" in payload:
        status = (clean_string(payload.get("status"), "Status", min_length=6, max_length=12) or "").title()
        if status not in USER_STATUSES:
            raise ValidationError("Invalid staff status.")
        staff.status = status
    if payload.get("password"):
        password = str(payload["password"])
        if len(password) < 8:
            raise ValidationError("Password must be at least 8 characters.",
                                  fields={"password": "Minimum 8 characters required."})
        staff.set_password(password)
    commit()
    cache.invalidate_prefix("users")
    return success_response(staff.to_dict(include_private=True), "Staff updated successfully")


# ------------------------------------------------------------- user management
@admin_bp.get("/users")
@admin_required
def list_users():
    query = User.query.filter(User.role.in_([ROLE_USER]))
    search = (request.args.get("search") or "").strip()
    status = (request.args.get("status") or "").strip().title()
    if search:
        like = f"%{search.lower()}%"
        query = query.filter(db.or_(db.func.lower(User.full_name).like(like),
                                    db.func.lower(User.username).like(like),
                                    db.func.lower(User.email).like(like)))
    if status and status in USER_STATUSES:
        query = query.filter(User.status == status)
    query = query.order_by(User.created_at.desc())

    def serializer(user: User) -> dict:
        data = user.to_dict(include_private=True)
        data["total_bookings"] = Booking.query.filter_by(user_id=user.id).count()
        data["active_bookings"] = Booking.query.filter_by(user_id=user.id, status=BOOKING_BOOKED).count()
        return data

    return success_response(paginate(query, serializer), "Users loaded")


@admin_bp.patch("/users/<int:user_id>/status")
@admin_required
def set_user_status(user_id: int):
    user = db.session.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found.")
    if user.role == ROLE_ADMIN:
        raise ValidationError("The administrator account cannot be deactivated or blacklisted.", status=403)
    payload = get_json()
    new_status = (clean_string(payload.get("status"), "Status", min_length=6, max_length=12, required=True) or "").title()
    if new_status not in USER_STATUSES:
        raise ValidationError("Status must be Active, Deactivated or Blacklisted.",
                              fields={"status": "Invalid value"})

    user.status = new_status
    if new_status in (USER_DEACTIVATED, USER_BLACKLISTED):
        released = 0
        for booking in Booking.query.filter_by(user_id=user.id, status=BOOKING_BOOKED).all():
            if booking.trek and booking.trek.status != TREK_COMPLETED:
                booking.status = BOOKING_CANCELLED
                booking.cancelled_at = datetime.utcnow()
                booking.payment_status = "Refunded" if booking.payment_status == "Paid" else booking.payment_status
                if booking.trek.status != TREK_COMPLETED:
                    booking.trek.available_slots = min(booking.trek.available_slots + booking.participants,
                                                        booking.trek.total_slots)
                    released += 1
        db.session.commit()
        if released:
            cache.invalidate_prefix("treks:list")
        detail = f"{released} active booking(s) cancelled and slots released."
    else:
        detail = ""

    db.session.add(Notification(
        user_id=user.id,
        title=f"Account {new_status.lower()}",
        message=f"Your account status is now {new_status}." + (f" {detail}" if detail else ""),
        category="account",
    ))
    commit()
    _invalidate_stats()
    return success_response(user.to_dict(include_private=True), f"User marked as {new_status}")


@admin_bp.get("/users/<int:user_id>")
@admin_required
def user_detail(user_id: int):
    user = db.session.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found.")
    data = user.to_dict(include_private=True)
    data["bookings"] = [b.to_dict() for b in
                        Booking.query.filter_by(user_id=user_id).order_by(Booking.booking_date.desc()).limit(50).all()]
    if user.role == ROLE_STAFF:
        data["assigned_treks"] = [t.to_dict() for t in
                                  Trek.query.filter(Trek.assigned_staff_id == user_id).all()]
        data["assignments"] = [a.to_dict() for a in StaffAssignment.query.filter_by(staff_id=user_id).all()]
    return success_response(data, "User detail loaded")


# ------------------------------------------------------------------ assignments
@admin_bp.get("/assignments")
@admin_required
def list_assignments():
    query = StaffAssignment.query.order_by(StaffAssignment.assigned_at.desc())
    trek_id = to_int(request.args.get("trek_id"), "trek_id", minimum=1)
    staff_id = to_int(request.args.get("staff_id"), "staff_id", minimum=1)
    if trek_id:
        query = query.filter(StaffAssignment.trek_id == trek_id)
    if staff_id:
        query = query.filter(StaffAssignment.staff_id == staff_id)
    return success_response(paginate(query, lambda a: a.to_dict()), "Assignments loaded")


# ------------------------------------------------------------------------ misc
@admin_bp.get("/all-bookings")
@admin_required
def all_bookings():
    query = Booking.query.order_by(Booking.booking_date.desc())
    status = (request.args.get("status") or "").strip().title()
    if status:
        query = query.filter(Booking.status == status)
    trek_id = to_int(request.args.get("trek_id"), "trek_id", minimum=1)
    if trek_id:
        query = query.filter(Booking.trek_id == trek_id)
    return success_response(paginate(query, lambda b: b.to_dict(), default_per_page=20), "Bookings loaded")


@admin_bp.get("/search")
@admin_required
def global_search():
    """Search users, staff and treks in a single call (used by the navbar)."""
    term = (request.args.get("q") or "").strip()
    if len(term) < 2:
        return success_response({"query": term, "users": [], "staff": [], "treks": []}, "Type at least 2 characters")
    like = f"%{term.lower()}%"

    users = User.query.filter(User.role == ROLE_USER,
                              db.or_(db.func.lower(User.full_name).like(like),
                                     db.func.lower(User.username).like(like),
                                     db.func.lower(User.email).like(like))).limit(10).all()
    staff = User.query.filter(User.role == ROLE_STAFF,
                              db.or_(db.func.lower(User.full_name).like(like),
                                     db.func.lower(User.username).like(like),
                                     db.func.lower(User.email).like(like))).limit(10).all()
    treks = Trek.query.filter(db.or_(db.func.lower(Trek.name).like(like),
                                     db.func.lower(Trek.location).like(like),
                                     db.func.lower(db.coalesce(Trek.region, "")).like(like))).limit(10).all()

    return success_response({
        "query": term,
        "users": [u.to_dict() for u in users],
        "staff": [s.to_dict() for s in staff],
        "treks": [t.to_dict(include_stats=False) for t in treks],
    }, "Search results")


@admin_bp.get("/reports/monthly")
@admin_required
def monthly_report_preview():
    """Rendered HTML of the monthly activity report (same output Celery e-mails)."""
    from app.services.reports import build_monthly_report_html, collect_report_data, report_period

    month = request.args.get("month")  # YYYY-MM
    period = report_period(month)
    data = collect_report_data(period)
    html = build_monthly_report_html(period, data)
    return success_response({"period": period.label, "key": period.key, "html": html,
                             "summary": {k: v for k, v in data.items() if k != "summary_text"}},
                            "Report generated")


@admin_bp.post("/jobs/<job_name>")
@admin_required
def trigger_job(job_name: str):
    """Trigger a scheduled job through Celery (falls back to inline execution)."""
    from app.tasks import dispatch_job

    allowed = ("daily-reminders", "monthly-report")
    if job_name not in allowed:
        raise NotFoundError("Unknown job. Available: " + ", ".join(allowed))

    forced = (request.args.get("mode") or "").lower()
    mode = forced if forced in ("celery", "inline") else None

    outcome = dispatch_job(job_name, mode=mode)
    status_code = 202 if outcome.get("mode") == "celery" else 200
    message = (
        f"{job_name} queued on the Celery worker (task {outcome.get('task_id')})."
        if outcome.get("mode") == "celery"
        else f"{job_name} executed immediately: {outcome.get('detail', 'no workers running')}"
    )
    return success_response(outcome, message, status_code)


@admin_bp.get("/jobs")
@admin_required
def list_jobs():
    query = JobRun.query.order_by(JobRun.started_at.desc())
    return success_response(paginate(query, lambda j: j.to_dict(), default_per_page=20), "Job history loaded")


@admin_bp.get("/notifications/all")
@admin_required
def all_notifications():
    query = Notification.query.order_by(Notification.created_at.desc())
    return success_response(paginate(query, lambda n: n.to_dict(), default_per_page=20), "Notifications loaded")


@admin_bp.delete("/cache")
@admin_required
def clear_cache():
    cache.invalidate_prefix("treks")
    cache.invalidate_prefix("stats")
    cache.invalidate_prefix("users")
    return success_response({"backend": cache.backend}, "Application cache cleared")


# ------------------------------------------------------------- notifications
def _notifications_payload(user: User):
    query = Notification.query.filter_by(user_id=user.id).order_by(Notification.created_at.desc())
    include_read = (request.args.get("include_read") or "true").lower() in ("1", "true", "yes")
    if not include_read:
        query = query.filter(Notification.read.is_(False))
    data = paginate(query, lambda n: n.to_dict(), default_per_page=20)
    data["unread"] = Notification.query.filter_by(user_id=user.id, read=False).count()
    return data


@admin_bp.get("/notifications")
@login_required
def my_notifications():
    """Notifications for the logged-in user of any role."""
    return success_response(_notifications_payload(g.current_user), "Notifications loaded")


@admin_bp.patch("/notifications/read-all")
@login_required
def mark_notifications_read():
    count = Notification.query.filter_by(user_id=g.current_user.id, read=False).update({"read": True})
    db.session.commit()
    return success_response({"updated": count}, "Notifications marked as read")


@admin_bp.delete("/notifications/<int:notification_id>")
@login_required
def delete_notification(notification_id: int):
    note = db.session.get(Notification, notification_id)
    if note is None or note.user_id != g.current_user.id:
        raise NotFoundError("Notification not found.")
    db.session.delete(note)
    db.session.commit()
    return success_response(None, "Notification removed")
