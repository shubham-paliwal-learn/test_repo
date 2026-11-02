"""Staff resources: assigned treks, participant rosters and staff dashboard.

Trek mutations (slots / status) are handled by ``app/api/treks.py`` which already
enforces "only the assigned staff may manage a trek"; this blueprint adds the
staff-centric read endpoints used by the UI.
"""
from datetime import date

from flask import Blueprint, current_app, g, request

from app.api.helpers import paginate, success_response
from app.extensions import db
from app.models import BOOKING_BOOKED, Booking, StaffAssignment, Trek
from app.services.auth import staff_required
from app.services.cache_service import cache

staff_bp = Blueprint("staff", __name__, url_prefix="/api/staff")


def _assigned_treks_query(staff_id: int):
    support_ids = db.session.query(StaffAssignment.trek_id).filter_by(staff_id=staff_id)
    return Trek.query.filter(db.or_(Trek.assigned_staff_id == staff_id, Trek.id.in_(support_ids)))


@staff_bp.get("/dashboard")
@staff_required
def dashboard():
    """Assigned treks + registered-user counts for the logged-in staff member."""
    user = g.current_user

    def producer():
        treks = _assigned_treks_query(user.id).order_by(Trek.start_date.asc()).all()
        upcoming = [t for t in treks if t.start_date and t.start_date >= date.today()]
        active = [t for t in treks if t.status in ("Open", "Closed")]
        completed = [t for t in treks if t.status == "Completed"]
        registered = (
            db.session.query(db.func.count(Booking.id))
            .join(Trek, Booking.trek_id == Trek.id)
            .filter(Trek.assigned_staff_id == user.id, Booking.status == BOOKING_BOOKED)
            .scalar()
        )
        return {
            "staff": user.to_dict(include_private=True),
            "totals": {
                "assigned_treks": len(treks),
                "upcoming_treks": len(upcoming),
                "active_treks": len(active),
                "completed_treks": len(completed),
                "registered_users": int(registered or 0),
                "cache_backend": cache.backend,
            },
            "treks": [t.to_dict() for t in treks],
        }

    key = f"stats:staff:{user.id}"
    # staff dashboard is cached under the "stats:" prefix so any booking/trek
    # mutation invalidates it through the admin stats invalidation path.
    data = cache.memoize(key, producer, ttl=int(current_app.config.get("CACHE_TTL_SECONDS", 60)),
                         force_refresh=(request.args.get("refresh") or "").lower() in ("1", "true"))
    return success_response(data, "Staff dashboard loaded")


@staff_bp.get("/treks")
@staff_required
def assigned_treks():
    query = _assigned_treks_query(g.current_user.id).order_by(Trek.start_date.asc())
    status = (request.args.get("status") or "").strip().title()
    if status:
        query = query.filter(Trek.status == status)
    return success_response(paginate(query, lambda t: t.to_dict(), default_per_page=20),
                            "Assigned treks loaded")


@staff_bp.get("/treks/<int:trek_id>/roster")
@staff_required
def roster(trek_id: int):
    """Participant list for one of the staff member's treks."""
    from app.api.treks import _ensure_manageable, _get_trek_or_404

    trek = _get_trek_or_404(trek_id)
    _ensure_manageable(trek)

    query = Booking.query.filter_by(trek_id=trek_id).order_by(Booking.booking_date.asc())
    status = (request.args.get("status") or "").strip().title()
    if status:
        query = query.filter(Booking.status == status)

    data = paginate(query, lambda b: b.to_dict(), default_per_page=50)
    data["trek"] = trek.to_dict()
    data["summary"] = {
        "booked": Booking.query.filter_by(trek_id=trek_id, status=BOOKING_BOOKED).count(),
        "completed": Booking.query.filter_by(trek_id=trek_id, status="Completed").count(),
        "cancelled": Booking.query.filter_by(trek_id=trek_id, status="Cancelled").count(),
    }
    return success_response(data, "Roster loaded")
