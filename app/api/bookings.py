"""Booking resources: book / cancel / history, admin & staff views, async CSV export."""
from datetime import datetime, timezone

from flask import Blueprint, g, request

from app.api.helpers import (
    ValidationError,
    clean_string,
    commit,
    get_json,
    paginate,
    success_response,
    to_int,
)
from app.extensions import db
from app.models import (
    BOOKING_BOOKED,
    BOOKING_CANCELLED,
    BOOKING_COMPLETED,
    ROLE_STAFF,
    ROLE_USER,
    TREK_OPEN,
    Booking,
    Notification,
    StaffAssignment,
    Trek,
    User,
)
from app.services.auth import admin_or_staff_required, login_required
from app.services.cache_service import cache

bookings_bp = Blueprint("bookings", __name__, url_prefix="/api/bookings")


class NotFoundError(Exception):
    def __init__(self, message: str, status: int = 404):
        super().__init__(message)
        self.message = message
        self.status = status


def _invalidate_trek_caches(trek_id: int | None = None) -> None:
    cache.invalidate_prefix("treks:list")
    cache.delete_keys("treks:filters")
    if trek_id is not None:
        cache.delete_keys(f"treks:detail:{trek_id}")
    cache.invalidate_prefix("stats:")


# --------------------------------------------------------------------- booking
@bookings_bp.post("/")
@login_required
def create_booking():
    """Book a trek. Only Open treks, no overbooking, no duplicate bookings."""
    user = g.current_user
    if user.role != ROLE_USER:
        raise ValidationError("Only trekkers can create bookings.", status=403)

    payload = get_json()
    trek_id = to_int(payload.get("trek_id"), "Trek", minimum=1, required=True)
    participants = to_int(payload.get("participants"), "Participants", minimum=1, maximum=10) or 1
    notes = clean_string(payload.get("notes"), "Notes", min_length=0, max_length=500, required=False)

    trek = db.session.get(Trek, trek_id)
    if trek is None:
        raise NotFoundError("Trek not found.")

    if trek.status != TREK_OPEN:
        raise ValidationError(
            f"This trek cannot be booked right now (status: {trek.status}). Bookings are allowed only for "
            "Open treks.",
            fields={"status": f"Trek is {trek.status}"},
        )

    existing = Booking.query.filter_by(user_id=user.id, trek_id=trek.id).first()
    if existing and existing.status == BOOKING_BOOKED:
        raise ValidationError("You have already booked this trek.", fields={"trek_id": "Already booked"})
    if existing and existing.status == BOOKING_CANCELLED:
        raise ValidationError(
            "This booking was cancelled earlier; cancellations are final. Please contact the organizer.",
            fields={"trek_id": "Cancelled booking exists"},
        )

    if trek.available_slots < participants:
        raise ValidationError(
            f"Not enough slots available. Only {trek.available_slots} slot(s) left for '{trek.name}'.",
            fields={"participants": f"Maximum {max(trek.available_slots, 0)}"},
            status=409,
        )

    # Atomic-ish slot reservation inside the transaction.
    fresh = db.session.query(Trek).filter(Trek.id == trek.id).with_for_update().first() \
        if db.engine.dialect.name != "sqlite" else trek
    if fresh.available_slots < participants:
        raise ValidationError("Slots just ran out. Please try another trek.", status=409)
    fresh.available_slots = max(fresh.available_slots - participants, 0)

    booking = Booking(
        user_id=user.id,
        trek_id=fresh.id,
        status=BOOKING_BOOKED,
        participants=participants,
        amount=round((fresh.base_price or 0.0) * participants, 2),
        payment_status="Pending" if fresh.base_price else "Not Required",
        notes=notes,
        booking_date=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.session.add(booking)
    db.session.add(
        Notification(
            user_id=user.id,
            title="Booking confirmed",
            message=(
                f"You are booked for '{fresh.name}' ({fresh.location}) starting {fresh.start_date}. "
                f"Booking ID BKG{booking.id or ''} – slots reserved: {participants}."
            ),
            category="booking",
        )
    )
    commit()
    _invalidate_trek_caches(fresh.id)
    return success_response(booking.to_dict(), "Booking created successfully", 201)


@bookings_bp.get("/my")
@login_required
def my_bookings():
    """Complete trekking history of the logged-in trekker."""
    user = g.current_user
    query = Booking.query.filter_by(user_id=user.id).order_by(Booking.booking_date.desc())
    status = (request.args.get("status") or "").strip().title()
    if status:
        query = query.filter(Booking.status == status)
    data = paginate(query, lambda b: b.to_dict())
    data["summary"] = {
        "total": Booking.query.filter_by(user_id=user.id).count(),
        "booked": Booking.query.filter_by(user_id=user.id, status=BOOKING_BOOKED).count(),
        "completed": Booking.query.filter_by(user_id=user.id, status=BOOKING_COMPLETED).count(),
        "cancelled": Booking.query.filter_by(user_id=user.id, status=BOOKING_CANCELLED).count(),
    }
    return success_response(data, "Bookings loaded")


@bookings_bp.get("/<int:booking_id>")
@login_required
def get_booking(booking_id: int):
    booking = db.session.get(Booking, booking_id)
    if booking is None:
        raise NotFoundError("Booking not found.")
    user = g.current_user
    if user.role == ROLE_USER and booking.user_id != user.id:
        raise NotFoundError("Booking not found.")
    if user.role == ROLE_STAFF:
        _ensure_staff_can_view(booking.trek)
    return success_response(booking.to_dict(), "Booking loaded")


@bookings_bp.patch("/<int:booking_id>/cancel")
@login_required
def cancel_booking(booking_id: int):
    """Trekker cancels own booking; admin may cancel any booking."""
    booking = db.session.get(Booking, booking_id)
    if booking is None:
        raise NotFoundError("Booking not found.")
    user = g.current_user

    if user.role == ROLE_USER and booking.user_id != user.id:
        raise NotFoundError("Booking not found.")
    if user.role == ROLE_STAFF:
        raise ValidationError("Staff members cannot cancel bookings. Ask the admin.", status=403)
    if booking.status != BOOKING_BOOKED:
        raise ValidationError(f"Booking is already {booking.status.lower()} and cannot be cancelled.")

    if booking.trek.start_date:
        days_to_start = (booking.trek.start_date - datetime.utcnow().date()).days
        if days_to_start < 0:
            raise ValidationError("The trek has already started; cancellation is no longer possible.")

    booking.status = BOOKING_CANCELLED
    booking.cancelled_at = datetime.now(timezone.utc).replace(tzinfo=None)
    booking.payment_status = "Refunded" if booking.payment_status == "Paid" else booking.payment_status

    trek = booking.trek
    trek.available_slots = min(trek.available_slots + booking.participants, trek.total_slots)

    db.session.add(
        Notification(
            user_id=booking.user_id,
            title="Booking cancelled",
            message=f"Your booking for '{trek.name}' has been cancelled. Slots released.",
            category="booking",
        )
    )
    commit()
    _invalidate_trek_caches(trek.id)
    return success_response(booking.to_dict(), "Booking cancelled successfully")


@bookings_bp.patch("/<int:booking_id>/payment")
@login_required
def pay_booking(booking_id: int):
    """Basic payment simulation."""
    booking = db.session.get(Booking, booking_id)
    if booking is None:
        raise NotFoundError("Booking not found.")
    user = g.current_user
    if user.role == ROLE_USER and booking.user_id != user.id:
        raise NotFoundError("Booking not found.")
    if booking.status != BOOKING_BOOKED:
        raise ValidationError("Payment can be made only for an active booking.")
    if booking.payment_status == "Paid":
        raise ValidationError("This booking is already paid.")
    booking.payment_status = "Paid"
    commit()
    return success_response(booking.to_dict(), f"Payment of ₹{booking.amount:.2f} recorded successfully")


# ------------------------------------------------------------- staff / admin
@bookings_bp.get("/")
@admin_or_staff_required
def list_bookings():
    """Admin sees everything; staff sees bookings for assigned treks only."""
    user = g.current_user
    query = Booking.query
    if user.role == ROLE_STAFF:
        trek_ids = db.session.query(StaffAssignment.trek_id).filter(StaffAssignment.staff_id == user.id)
        query = query.join(Trek, Booking.trek_id == Trek.id).filter(
            db.or_(Trek.assigned_staff_id == user.id, Booking.trek_id.in_(trek_ids))
        )

    status = (request.args.get("status") or "").strip().title()
    if status:
        query = query.filter(Booking.status == status)
    payment = (request.args.get("payment_status") or "").strip().title()
    if payment:
        query = query.filter(Booking.payment_status == payment)
    trek_id = to_int(request.args.get("trek_id"), "trek_id", minimum=1)
    if trek_id:
        query = query.filter(Booking.trek_id == trek_id)
    user_id = to_int(request.args.get("user_id"), "user_id", minimum=1)
    if user_id:
        query = query.filter(Booking.user_id == user_id)
    search = (request.args.get("search") or "").strip()
    if search:
        like = f"%{search.lower()}%"
        query = query.join(User, Booking.user_id == User.id).filter(
            db.or_(db.func.lower(User.full_name).like(like), db.func.lower(User.email).like(like),
                   db.func.lower(User.username).like(like))
        )

    order = Booking.booking_date.desc() if (request.args.get("order", "desc") == "desc") else Booking.booking_date.asc()
    query = query.order_by(order)
    return success_response(paginate(query, lambda b: b.to_dict()), "Bookings loaded")


@bookings_bp.patch("/<int:booking_id>/status")
@admin_or_staff_required
def update_booking_status(booking_id: int):
    """Staff/admin mark a participant's booking Completed (attendance) or Cancelled."""
    booking = db.session.get(Booking, booking_id)
    if booking is None:
        raise NotFoundError("Booking not found.")
    user = g.current_user
    if user.role == ROLE_STAFF:
        _ensure_staff_can_manage(booking.trek)

    payload = get_json()
    new_status = (clean_string(payload.get("status"), "Status", min_length=7, max_length=12, required=True) or "").title()
    if new_status not in (BOOKING_COMPLETED, BOOKING_CANCELLED, BOOKING_BOOKED):
        raise ValidationError("Booking status must be Booked, Completed or Cancelled.")

    if new_status == booking.status:
        raise ValidationError(f"Booking is already {booking.status}.")

    if new_status == BOOKING_CANCELLED:
        booking.trek.available_slots = min(booking.trek.available_slots + booking.participants,
                                           booking.trek.total_slots)
        booking.cancelled_at = datetime.now(timezone.utc).replace(tzinfo=None)
    elif new_status == BOOKING_BOOKED and booking.status == BOOKING_CANCELLED:
        if booking.trek.available_slots < booking.participants:
            raise ValidationError("No slots available to reinstate this booking.", status=409)
        booking.trek.available_slots -= booking.participants
        booking.cancelled_at = None

    booking.status = new_status
    db.session.add(
        Notification(
            user_id=booking.user_id,
            title=f"Booking {new_status.lower()}",
            message=f"Your booking for '{booking.trek.name}' is now marked {new_status}.",
            category="booking",
        )
    )
    commit()
    _invalidate_trek_caches(booking.trek_id)
    return success_response(booking.to_dict(), f"Booking marked as {new_status}")


def _ensure_staff_can_view(trek: Trek) -> None:
    user = g.current_user
    if user.role == "admin":
        return
    if trek.assigned_staff_id == user.id:
        return
    if StaffAssignment.query.filter_by(trek_id=trek.id, staff_id=user.id).first():
        return
    raise ValidationError("You are not assigned to this trek.", status=403)


_ensure_staff_can_manage = _ensure_staff_can_view


# ------------------------------------------------------------------ CSV export
@bookings_bp.post("/export")
@login_required
def export_bookings():
    """Trigger the async Celery batch job that builds the user's trekking history CSV."""
    from app.tasks import export_booking_history

    user = g.current_user
    target_user_id = user.id
    if user.role in ("admin", "staff"):
        target_user_id = to_int(request.args.get("user_id"), "user_id", minimum=1) or user.id

    task = export_booking_history.delay(target_user_id)
    return success_response(
        {"task_id": task.id, "user_id": target_user_id, "state": task.state},
        "Export started. You will be notified when the CSV is ready.",
        202,
    )


@bookings_bp.get("/export/<task_id>")
@login_required
def export_status(task_id: str):
    """Poll the async export job status / download link."""
    from celery.result import AsyncResult

    from app.tasks import celery_app

    result = AsyncResult(task_id, app=celery_app)
    payload = {"task_id": task_id, "state": result.state}
    if result.successful():
        payload["result"] = result.result
        payload["download_url"] = f"/api/bookings/download/{task_id}"
    elif result.failed():
        payload["error"] = str(result.result)
    return success_response(payload, "Export status")


@bookings_bp.get("/download/<task_id>")
@login_required
def download_export(task_id: str):
    """Serve the CSV produced by the background job (owner or admin only)."""
    import os

    from flask import send_file
    from celery.result import AsyncResult

    from app.tasks import celery_app

    result = AsyncResult(task_id, app=celery_app)
    if not result.successful():
        raise ValidationError("The export file is not ready yet.", status=404)

    meta = result.result or {}
    path = meta.get("path")
    owner_id = meta.get("user_id")
    if not path or not os.path.exists(path):
        raise NotFoundError("Export file not found. Please re-run the export.")
    if g.current_user.role == ROLE_USER and g.current_user.id != owner_id:
        raise NotFoundError("Export file not found.")
    return send_file(path, mimetype="text/csv", as_attachment=True,
                     download_name=os.path.basename(path))
