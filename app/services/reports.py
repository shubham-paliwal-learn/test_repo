"""Monthly activity report generation (Jinja2 HTML template).

Used both by the Celery scheduled job (e-mailed to the admin) and by the admin
UI preview endpoint.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from flask import current_app, render_template


@dataclass(frozen=True)
class ReportPeriod:
    key: str      # YYYY-MM
    label: str    # "October 2026"
    start: date
    end: date     # exclusive


def report_period(month: str | None = None) -> ReportPeriod:
    """Resolve ``YYYY-MM`` (default: previous month) into a period object."""
    today = date.today()
    if month:
        try:
            parsed = datetime.strptime(month, "%Y-%m").date()
        except ValueError:
            from app.api.helpers import ValidationError

            raise ValidationError("month must be in YYYY-MM format.", fields={"month": "Invalid format"})
        start = parsed.replace(day=1)
    else:
        start = today.replace(day=1)
    end = (start.replace(day=28) + timedelta(days=7)).replace(day=1)
    return ReportPeriod(key=start.strftime("%Y-%m"), label=start.strftime("%B %Y"), start=start, end=end)


def collect_report_data(period: ReportPeriod) -> dict:
    """Aggregate trekking statistics for the given month."""
    from app.extensions import db
    from app.models import BOOKING_CANCELLED, Booking, Trek, User

    start_dt = datetime.combine(period.start, datetime.min.time())
    end_dt = datetime.combine(period.end, datetime.min.time())

    treks_in_month = Trek.query.filter(Trek.start_date >= period.start, Trek.start_date < period.end).all()
    completed_treks = [t for t in treks_in_month if t.status == "Completed"]
    bookings_in_month = Booking.query.filter(Booking.booking_date >= start_dt,
                                             Booking.booking_date < end_dt).all()
    valid_bookings = [b for b in bookings_in_month if b.status != BOOKING_CANCELLED]

    popular_rows = (
        db.session.query(
            Trek.id, Trek.name, Trek.location, Trek.difficulty,
            db.func.count(Booking.id).label("bookings"),
            db.func.coalesce(db.func.sum(Booking.participants), 0).label("participants"),
            db.func.coalesce(db.func.sum(Booking.amount), 0.0).label("revenue"),
        )
        .join(Booking, Booking.trek_id == Trek.id)
        .filter(Booking.booking_date >= start_dt, Booking.booking_date < end_dt,
                Booking.status != BOOKING_CANCELLED)
        .group_by(Trek.id, Trek.name, Trek.location, Trek.difficulty)
        .order_by(db.desc("bookings"))
        .limit(10)
        .all()
    )

    new_trekkers = User.query.filter(User.role == "user", User.created_at >= start_dt,
                                     User.created_at < end_dt).count()

    difficulty_breakdown = {}
    for row in popular_rows:
        difficulty_breakdown[row.difficulty] = difficulty_breakdown.get(row.difficulty, 0) + row.bookings

    total_participants = sum(b.participants for b in valid_bookings)
    revenue = round(float(sum(b.amount for b in valid_bookings)), 2)

    summary_text = (
        f"Monthly activity report for {period.label}\n"
        f"Treks conducted: {len(completed_treks)} (scheduled: {len(treks_in_month)})\n"
        f"Bookings: {len(valid_bookings)} | Unique trekkers: {len({b.user_id for b in valid_bookings})}\n"
        f"Participants: {total_participants} | Revenue: {revenue:.2f}\n"
        f"New registrations: {new_trekkers}\n"
    )

    return {
        "period": {"key": period.key, "label": period.label,
                   "start": period.start.isoformat(), "end": (period.end - timedelta(days=1)).isoformat()},
        "treks_scheduled": len(treks_in_month),
        "treks_conducted": len(completed_treks),
        "open_treks": len([t for t in treks_in_month if t.status == "Open"]),
        "total_bookings": len(bookings_in_month),
        "valid_bookings": len(valid_bookings),
        "cancelled_bookings": len(bookings_in_month) - len(valid_bookings),
        "unique_trekkers": len({b.user_id for b in valid_bookings}),
        "total_participants": total_participants,
        "new_trekkers": new_trekkers,
        "revenue": revenue,
        "popular_treks": [
            {"name": r.name, "location": r.location, "difficulty": r.difficulty,
             "bookings": r.bookings, "participants": int(r.participants or 0),
             "revenue": round(float(r.revenue or 0), 2)}
            for r in popular_rows
        ],
        "difficulty_breakdown": difficulty_breakdown,
        "trek_lines": [{"name": t.name, "location": t.location, "status": t.status,
                        "start": t.start_date.isoformat() if t.start_date else "-",
                        "registered": t.booked_count, "slots": t.total_slots}
                       for t in treks_in_month],
        "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "summary_text": summary_text,
    }


def build_monthly_report_html(period: ReportPeriod, data: dict | None = None) -> str:
    """Render the HTML e-mail body through a Jinja2 template."""
    payload = data or collect_report_data(period)
    html = render_template("reports/monthly.html", report=payload, site_name="Trekking Management Application")
    return html
