"""Celery application + background/scheduled jobs.

Jobs
----
* ``send_daily_reminders``  - scheduled daily; e-mails/G-Chat reminders about
  treks starting within the next 3 days to every participant.
* ``generate_monthly_report`` - scheduled on the 1st of each month; builds an
  HTML activity report (Jinja2 template) and e-mails it to the admin.
* ``export_booking_history`` - user triggered; writes the trekker's booking
  history to a CSV file and creates an in-app notification with the download link.

Every task is wrapped by ``flask_app.app_context()`` so SQLAlchemy works inside
the worker, and each run is recorded in the ``job_runs`` table for visibility.
"""
import os
from datetime import date, datetime, timedelta

from celery import Celery
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
DEFAULT_EXPORT_DIR = os.path.join(BASE_DIR, "instance", "exports")


def _export_dir() -> str:
    """Resolve the export directory from Flask config with a safe fallback."""
    try:
        return _get_flask_app().config.get("EXPORT_DIR", DEFAULT_EXPORT_DIR)
    except Exception:  # pragma: no cover - app not built yet
        return DEFAULT_EXPORT_DIR


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


# --------------------------------------------------------------------- celery
celery_app = Celery(
    "tma",
    broker=_env("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=_env("CELERY_RESULT_BACKEND", "redis://localhost:6379/0"),
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone=_env("CELERY_TIMEZONE", "Asia/Kolkata"),
    enable_utc=True,
    task_track_started=True,
    result_expires=60 * 60 * 24,
    broker_connection_retry_on_startup=True,
    task_always_eager=False,
)

TASK_BY_JOB = {
    "daily-reminders": "app.tasks.send_daily_reminders",
    "monthly-report": "app.tasks.generate_monthly_report",
}


def make_celery(app=None):  # pragma: no cover - kept for parity/tests
    """Return the module level Celery app (tasks look up the Flask app lazily)."""
    return celery_app


def _get_flask_app():
    """Build (once per process) the Flask app so tasks can use the models."""
    global _FLASK_APP
    if _FLASK_APP is None:
        from app.main import create_app

        _FLASK_APP = create_app()
    return _FLASK_APP


_FLASK_APP = None


# --------------------------------------------------------------- job tracking
class JobRecorder:
    def __init__(self, name: str):
        self.name = name
        self.run = None

    def __enter__(self):
        from app.extensions import db
        from app.models import JobRun

        self.run = JobRun(job_name=self.name, status="started")
        db.session.add(self.run)
        db.session.commit()
        return self

    def finish(self, status: str = "success", detail: str = "") -> None:
        from app.extensions import db
        from app.models import JobRun

        run = db.session.get(JobRun, self.run.id) if self.run else None
        if run is not None:
            run.status = status
            run.detail = (detail or "")[:1000]
            run.finished_at = datetime.utcnow()
            db.session.commit()


# ------------------------------------------------------------------ utilities
def _upcoming_bookings(days_ahead: int = 3):
    """Active bookings whose trek starts within ``days_ahead`` days."""
    from app.models import BOOKING_BOOKED, Booking, Trek

    today = date.today()
    horizon = today + timedelta(days=days_ahead)
    return (
        Booking.query.join(Trek, Booking.trek_id == Trek.id)
        .filter(Booking.status == BOOKING_BOOKED, Trek.start_date >= today, Trek.start_date <= horizon)
        .order_by(Trek.start_date.asc())
        .all()
    )


# --------------------------------------------------------------------- tasks
@celery_app.task(name="app.tasks.send_daily_reminders", bind=True, max_retries=1)
def send_daily_reminders(self, days_ahead: int = 3):
    """Scheduled daily: remind trekkers about upcoming treks (mail + G-Chat)."""
    with _get_flask_app().app_context():
        from app.services.notifications import send_gchat_message, send_mail

        recorder = JobRecorder("daily-reminders")
        with recorder:
            bookings = _upcoming_bookings(days_ahead)
            grouped: dict[int, list] = {}
            for booking in bookings:
                grouped.setdefault(booking.user_id, []).append(booking)

            sent = 0
            lines = []
            for user_id, user_bookings in grouped.items():
                user = db_get_user(user_id)
                if user is None:
                    continue
                body_lines = []
                for booking in user_bookings:
                    trek = booking.trek
                    days = (trek.start_date - date.today()).days
                    body_lines.append(
                        f"- {trek.name} ({trek.location}) starts {trek.start_date.isoformat()} "
                        f"({'today' if days == 0 else f'in {days} day(s)'})."
                        + (f" Instructions: {trek.instructions}" if trek.instructions else "")
                    )
                message = "Upcoming trek reminder:\n" + "\n".join(body_lines)
                delivered = send_mail(
                    to=user.email,
                    subject="TMA - Upcoming trek reminder",
                    text=message,
                )
                db_add_notification(
                    user_id=user.id,
                    title="Upcoming trek reminder",
                    message=message,
                    category="reminder",
                )
                sent += 1
                lines.append(f"{user.username}: {len(user_bookings)} trek(s), email={delivered}")

            summary = f"{sent} trekker(s) reminded across {len(bookings)} booking(s)."
            webhook_result = None
            if lines:
                webhook_result = send_gchat_message(
                    "*Daily trek reminders*\n" + "\n".join(lines) + f"\n\n{summary}"
                )
            recorder.finish("success", summary + (f" | gchat={webhook_result}" if webhook_result else ""))
            return {"job": "daily-reminders", "reminded": sent, "bookings": len(bookings),
                    "gchat": webhook_result, "detail": summary}


def db_get_user(user_id: int):
    from app.extensions import db
    from app.models import User

    return db.session.get(User, user_id)


def db_add_notification(user_id: int, title: str, message: str, category: str):
    from app.extensions import db
    from app.models import Notification

    db.session.add(Notification(user_id=user_id, title=title, message=message, category=category))
    db.session.commit()


@celery_app.task(name="app.tasks.generate_monthly_report", bind=True)
def generate_monthly_report(self, month: str | None = None):
    """Scheduled monthly: build the HTML activity report and e-mail the admin."""
    with _get_flask_app().app_context():
        from app.services.reports import build_monthly_report_html, collect_report_data, report_period
        from app.services.notifications import send_mail, send_gchat_message

        period = report_period(month)
        recorder = JobRecorder("monthly-report")
        with recorder:
            html = build_monthly_report_html(period)
            data = collect_report_data(period)
            path = _write_report_file(period, html)
            admin_email = _get_flask_app().config.get("ADMIN_EMAIL")
            delivered = send_mail(
                to=admin_email,
                subject=f"TMA monthly activity report - {period.label}",
                text=data["summary_text"],
                html=html,
            )
            send_gchat_message(f"*Monthly report* {period.label} generated and mailed to {admin_email}.")
            detail = (f"{period.label}: treks={data['treks_conducted']}, participants="
                      f"{data['total_participants']}, emailed={delivered}")
            recorder.finish("success", detail)
            return {"job": "monthly-report", "period": period.label, "path": path,
                    "emailed": delivered, "detail": detail}


def _write_report_file(period, html: str) -> str:
    export_dir = _export_dir()
    os.makedirs(export_dir, exist_ok=True)
    path = os.path.join(export_dir, f"monthly_report_{period.key}.html")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(html)
    return path


@celery_app.task(name="app.tasks.export_booking_history", bind=True)
def export_booking_history(self, user_id: int):
    """User triggered: write the trekker's history to CSV + notify when done."""
    with _get_flask_app().app_context():
        import csv

        from app.extensions import db
        from app.models import Booking, Notification, User

        user = db.session.get(User, user_id)
        if user is None:
            raise ValueError(f"User {user_id} does not exist")

        export_dir = _export_dir()
        os.makedirs(export_dir, exist_ok=True)
        filename = f"booking_history_{user.username}_{date.today().isoformat()}.csv"
        path = os.path.join(export_dir, filename)

        query = (
            Booking.query.filter_by(user_id=user_id)
            .order_by(Booking.booking_date.desc())
            .all()
        )
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow([
                "User ID", "User Name", "Booking ID", "Trek ID", "Trek Name", "Location",
                "Difficulty", "Duration (days)", "Participants", "Booking Date",
                "Trek Start Date", "Trek End Date", "Booking Status", "Payment Status", "Amount",
            ])
            for booking in query:
                trek = booking.trek
                writer.writerow([
                    booking.user_id,
                    user.full_name,
                    f"BKG{booking.id:05d}",
                    f"TRK{trek.id:04d}" if trek else "",
                    trek.name if trek else "",
                    trek.location if trek else "",
                    trek.difficulty if trek else "",
                    trek.duration_days if trek else "",
                    booking.participants,
                    booking.booking_date.strftime("%Y-%m-%d %H:%M") if booking.booking_date else "",
                    trek.start_date.isoformat() if trek and trek.start_date else "",
                    trek.end_date.isoformat() if trek and trek.end_date else "",
                    booking.status,
                    booking.payment_status,
                    f"{booking.amount:.2f}",
                ])

        db.session.add(Notification(
            user_id=user_id,
            title="Booking history exported",
            message=(
                f"Your trekking history CSV ({len(query)} row(s)) is ready. "
                f"Download it from the History page or via /api/bookings/download/{self.request.id}."
            ),
            category="export",
        ))
        db.session.commit()

        return {
            "user_id": user_id,
            "rows": len(query),
            "path": path,
            "filename": filename,
            "task_id": self.request.id,
        }


# ------------------------------------------------------------ dispatch helper
def broker_is_available() -> bool:
    """Cheap probe so the API can fall back to inline execution when needed."""
    try:
        backend = _env("CELERY_BROKER_URL", str(celery_app.conf.broker_connection().url()))
        if not backend or backend.startswith("memory"):
            return False
        import redis

        client = redis.from_url(backend, socket_connect_timeout=1, socket_timeout=1)
        client.ping()
        # Also require a live worker, otherwise the task would sit in the queue.
        inspect = celery_app.control.inspect(timeout=1)
        return bool(inspect.ping())
    except Exception:
        return False


def dispatch_job(job_name: str, mode: str | None = None) -> dict:
    """Queue a scheduled job on Celery, or run it inline when unavailable."""
    if job_name not in TASK_BY_JOB:
        raise ValueError(f"Unknown job: {job_name}")

    chosen = mode or ("celery" if broker_is_available() else "inline")
    if chosen == "celery":
        result = celery_app.send_task(TASK_BY_JOB[job_name])
        return {"mode": "celery", "task_id": result.id, "job": job_name}

    payload = run_job_inline(job_name)
    return {"mode": "inline", "task_id": None, "job": job_name, **payload}


def run_job_inline(job_name: str) -> dict:
    """Synchronous execution used by the CLI and as a Celery fallback."""
    with _get_flask_app().app_context():
        if job_name == "daily-reminders":
            return send_daily_reminders.run_inline()
        return generate_monthly_report.run_inline()


def _inline_shim(task, *args, **kwargs):
    """Execute a bound Celery task without a broker."""
    class _Request:
        id = f"inline-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

    task.request = _Request()  # type: ignore[attr-defined]
    return task(*args, **kwargs)


def _install_run_inline():
    """Attach ``run_inline`` helpers so callers can execute tasks synchronously."""
    send_daily_reminders.run_inline = lambda *a, **k: _inline_shim(send_daily_reminders, *a, **k)
    generate_monthly_report.run_inline = lambda *a, **k: _inline_shim(generate_monthly_report, *a, **k)
    export_booking_history.run_inline = lambda *a, **k: _inline_shim(export_booking_history, *a, **k)


_install_run_inline()
