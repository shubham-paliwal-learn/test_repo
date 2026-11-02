"""Application factory: extensions, blueprints, error handlers, CLI, admin bootstrap."""
import os
from datetime import datetime

from flask import Flask, jsonify

from app.config import Config, TestConfig  # noqa: F401  (re-exported for convenience)
from app.extensions import cors, db
from app.services.cache_service import cache


def create_app(config_object: type | str | None = None) -> Flask:
    """Create and configure the Flask application.

    ``config_object`` may be a config class (e.g. ``TestConfig``) or an import
    string.  When omitted, the ``FLASK_CONFIG`` environment variable selects
    between ``development``, ``production`` and ``test``.
    """
    app = Flask(__name__, instance_path=os.path.join(os.path.abspath(os.getcwd()), "instance"))

    if isinstance(config_object, type):
        app.config.from_object(config_object)
    elif config_object:
        app.config.from_object(config_object)
    else:
        env = os.environ.get("FLASK_CONFIG", "development").lower()
        if env == "test":
            app.config.from_object(TestConfig)
        else:
            app.config.from_object(Config)
        app.config.from_prefixed_env()  # TMA_* environment overrides

    _ensure_instance_dir(app)

    # ------------------------------------------------------------- extensions
    db.init_app(app)
    cors.init_app(
        app,
        resources={r"/api/*": {"origins": "*"}},
        expose_headers=["Content-Disposition"],
    )
    cache.init_app(app)

    # -------------------------------------------------------------- blueprints
    from app.api.admin import admin_bp
    from app.api.auth import auth_bp
    from app.api.bookings import bookings_bp
    from app.api.staff import staff_bp
    from app.api.treks import treks_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(treks_bp)
    app.register_blueprint(bookings_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(staff_bp)

    _register_error_handlers(app)
    _register_cli(app)
    _register_scheduled_jobs(app)

    with app.app_context():
        # NOTE: bind to a different name -- plain ``import app.models`` rebinds the
        # local variable ``app`` to the *package* module, so the function would end
        # up returning that module instead of the Flask object
        # (AttributeError: module 'app' has no attribute 'test_client' / 'route').
        import app.models as tma_models  # noqa: F401  ensure every model is registered

        db.create_all()          # programmatic database creation (no manual DB tools)
        _bootstrap_admin()       # exactly one pre-existing admin
        _seed_demo_data_if_empty()

    return app


def _ensure_instance_dir(app: Flask) -> None:
    uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if uri.startswith("sqlite:///"):
        path = uri.replace("sqlite:///", "", 1)
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
    os.makedirs(os.path.join(app.root_path, "..", "logs"), exist_ok=True)


# --------------------------------------------------------------------- errors
def _register_error_handlers(app: Flask) -> None:
    """Uniform JSON error payloads for every exception type used by the APIs."""
    from app.api import bookings as bookings_module
    from app.api import treks as treks_module
    from app.api.helpers import NotFoundError, ValidationError

    def validation_handler(exc):
        return (
            jsonify({"success": False, "message": exc.message,
                     "errors": getattr(exc, "fields", {}) or {}}),
            getattr(exc, "status", 400),
        )

    def not_found_handler(exc):
        return jsonify({"success": False, "message": exc.message, "errors": {}}), \
            getattr(exc, "status", 404)

    # ``treks``/``bookings`` define their own ValidationError/NotFoundError
    # classes; register handlers for all of them so responses stay consistent.
    for exc_cls in (ValidationError, treks_module.ValidationError, bookings_module.ValidationError):
        app.errorhandler(exc_cls)(validation_handler)
    for exc_cls in (NotFoundError, treks_module.NotFoundError, bookings_module.NotFoundError):
        app.errorhandler(exc_cls)(not_found_handler)

    @app.errorhandler(404)
    def _http_404(_exc):
        return jsonify({"success": False, "message": "Resource not found.", "errors": {}}), 404

    @app.errorhandler(405)
    def _http_405(_exc):
        return jsonify({"success": False, "message": "Method not allowed.", "errors": {}}), 405

    @app.errorhandler(Exception)
    def _unhandled(exc):  # pragma: no cover - safety net
        db.session.rollback()
        app.logger.exception("Unhandled error: %s", exc)
        message = str(exc) if app.debug else "Internal server error. Please try again later."
        return jsonify({"success": False, "message": message, "errors": {}}), 500


# ------------------------------------------------------------------------ CLI
def _register_cli(app: Flask) -> None:
    import click

    @app.cli.command("init-db")
    def init_db_command():
        """Drop and recreate the database programmatically, then seed demo data."""
        db.drop_all()
        db.create_all()
        _bootstrap_admin()
        _seed_demo_data_if_empty()
        click.echo("Database created and seeded.")

    @app.cli.command("run-job")
    @click.argument("job_name", type=click.Choice(["daily-reminders", "monthly-report"]))
    def run_job_command(job_name: str):
        """Run a scheduled job synchronously (used when Celery/Redis is not running)."""
        if job_name == "daily-reminders":
            from app.tasks import send_daily_reminders

            result = send_daily_reminders.run_inline()
        else:
            from app.tasks import generate_monthly_report

            result = generate_monthly_report.run_inline()
        app.logger.info("%s", result)
        click.echo(str(result))

    @app.cli.command("seed-demo")
    def seed_command():
        """Insert sample staff/treks so the UI can be demonstrated immediately."""
        count = _seed_demo_data_if_empty(force=True)
        click.echo(f"Seeded {count} demo record set(s).")


# ------------------------------------------------------------ admin bootstrap
def _bootstrap_admin() -> None:
    """Create the single pre-existing Admin after DB creation (no registration)."""
    from flask import current_app

    from app.models import ROLE_ADMIN, USER_ACTIVE, User

    existing_admins = User.query.filter_by(role=ROLE_ADMIN).all()
    if existing_admins:
        # Enforce "only one admin must exist".
        keeper = existing_admins[0]
        for extra in existing_admins[1:]:
            db.session.delete(extra)
        if len(existing_admins) > 1:
            db.session.commit()
        return

    username = current_app.config["ADMIN_USERNAME"]
    email = current_app.config["ADMIN_EMAIL_BOOTSTRAP"]
    admin = User(
        username=username,
        email=email,
        full_name="System Administrator",
        role=ROLE_ADMIN,
        status=USER_ACTIVE,
        phone="+91-9000000000",
        specialization="Platform Administration",
        contact_details="admin@trekking.local",
    )
    admin.set_password(current_app.config["ADMIN_PASSWORD"])
    db.session.add(admin)
    db.session.commit()


# ------------------------------------------------------------------ demo data
def _seed_demo_data_if_empty(force: bool = False) -> int:
    """Seed a handful of staff/treks/bookings so demos work out of the box."""
    from flask import current_app

    from app.models import (
        ROLE_STAFF,
        ROLE_USER,
        TREK_APPROVED,
        TREK_COMPLETED,
        TREK_OPEN,
        TREK_PENDING,
        Booking,
        StaffAssignment,
        Trek,
        User,
    )

    if not force and User.query.filter(User.role.in_([ROLE_STAFF, ROLE_USER])).first() is not None:
        return 0
    if not force and current_app.config.get("TESTING"):
        return 0

    from datetime import date, timedelta

    today = date.today()

    staff_specs = [
        ("staff.arun", "Arun Kumar", "High Altitude Leadership", "+91-9812345671"),
        ("staff.meera", "Meera Nair", "Navigation & Safety", "+91-9812345672"),
        ("staff.rohit", "Rohit Sharma", "Wilderness First Aid", "+91-9812345673"),
    ]
    staff_members = []
    for username, name, spec, phone in staff_specs:
        user = User.query.filter_by(username=username).first()
        if user is None:
            user = User(
                username=username,
                email=f"{username}@trekking.local",
                full_name=name,
                role=ROLE_STAFF,
                specialization=spec,
                contact_details=phone,
                phone=phone,
            )
            user.set_password("Staff@123")
            db.session.add(user)
            db.session.flush()
        staff_members.append(user)

    trekkers = []
    for idx, (username, name) in enumerate(
        [("trek.ravi", "Ravi Teja"), ("trek.anita", "Anita Desai"), ("trek.kabir", "Kabir Khan")]
    ):
        user = User.query.filter_by(username=username).first()
        if user is None:
            user = User(
                username=username,
                email=f"{username}@trekking.local",
                full_name=name,
                role=ROLE_USER,
                phone=f"+91-99000000{idx:02d}",
            )
            user.set_password("Trek@1234")
            db.session.add(user)
            db.session.flush()
        trekkers.append(user)

    trek_rows = [
        dict(name="Hampta Pass Trek", location="Kullu, Himachal Pradesh", region="Himalayas",
             difficulty="Moderate", duration_days=5, total_slots=20,
             start_date=today + timedelta(days=6), end_date=today + timedelta(days=10),
             base_price=12500.0, min_age=14, status=TREK_OPEN, staff=0,
             description="Crosses the Hampta pass with lush valleys and dramatic ridgelines.",
             instructions="Carry thermal layers, rain shell and broken-in boots."),
        dict(name="Valley of Flowers Trek", location="Uttarakhand", region="Himalayas",
             difficulty="Easy", duration_days=6, total_slots=25,
             start_date=today + timedelta(days=12), end_date=today + timedelta(days=17),
             base_price=9800.0, min_age=12, status=TREK_OPEN, staff=1,
             description="UNESCO World Heritage alpine meadow famous for endemic blooms.",
             instructions="Acclimatise at Govindghat; carry sunglasses and sunscreen."),
        dict(name="Roopkund Trek", location="Chamoli, Uttarakhand", region="Himalayas",
             difficulty="Hard", duration_days=8, total_slots=15,
             start_date=today + timedelta(days=20), end_date=today + timedelta(days=27),
             base_price=16500.0, min_age=16, status=TREK_APPROVED, staff=2,
             description="Mystery-skeleton lake trek at 15,700 ft with steep glacier sections.",
             instructions="Prior high-altitude experience recommended."),
        dict(name="Sahyadri Weekend Trek", location="Maharashtra", region="Western Ghats",
             difficulty="Easy", duration_days=2, total_slots=30,
             start_date=today + timedelta(days=3), end_date=today + timedelta(days=4),
             base_price=2400.0, min_age=10, status=TREK_OPEN, staff=0,
             description="Fort-and-waterfall circuit in the Sahyadris close to Pune/Mumbai.",
             instructions="Start early; carry 2L water per person."),
        dict(name="Chadar Frozen River Trek", location="Ladakh", region="Trans-Himalaya",
             difficulty="Hard", duration_days=9, total_slots=12,
             start_date=today + timedelta(days=35), end_date=today + timedelta(days=43),
             base_price=24500.0, min_age=18, status=TREK_PENDING, staff=1,
             description="Walk on the frozen Zanskar river through ice caves.",
             instructions="Crampons and thermos provided by the organisers."),
        dict(name="Kodachadri Backwoods Trek", location="Karnataka", region="Western Ghats",
             difficulty="Moderate", duration_days=3, total_slots=18,
             start_date=today - timedelta(days=21), end_date=today - timedelta(days=19),
             base_price=4200.0, min_age=12, status=TREK_COMPLETED, staff=2,
             description="Sholava forest trail to the Nirmala Bhadrakali temple summit.",
             instructions="Monsoon leeches expected; gaiters advised."),
    ]

    created_treks = []
    for row in trek_rows:
        staff = staff_members[row.pop("staff")]
        trek = Trek.query.filter_by(name=row["name"]).first()
        if trek is None:
            trek = Trek(**row, assigned_staff_id=staff.id, created_by=User.query.filter_by(role="admin").first().id)
            trek.available_slots = trek.total_slots
            db.session.add(trek)
            db.session.flush()
            db.session.add(StaffAssignment(trek_id=trek.id, staff_id=staff.id, role_label="Lead"))
            if staff not in trek.support_staff:
                trek.support_staff.append(staff)
        created_treks.append(trek)

    # A couple of demo bookings so dashboards/reports have content.
    open_treks = [t for t in created_treks if t.status == TREK_OPEN]
    completed = [t for t in created_treks if t.status == TREK_COMPLETED]
    for trek, trekker in zip(open_treks, trekkers):
        if Booking.query.filter_by(user_id=trekker.id, trek_id=trek.id).first() is None:
            booking = Booking(
                user_id=trekker.id, trek_id=trek.id, participants=1,
                amount=trek.base_price, payment_status="Paid", status="Booked",
                notes="Demo booking created during seeding.",
            )
            db.session.add(booking)
            trek.available_slots = max(trek.available_slots - 1, 0)
    if completed and trekkers:
        trek = completed[0]
        if Booking.query.filter_by(user_id=trekkers[0].id, trek_id=trek.id).first() is None:
            db.session.add(Booking(user_id=trekkers[0].id, trek_id=trek.id, status="Completed",
                                   participants=1, amount=trek.base_price, payment_status="Paid"))
            trek.available_slots = max(trek.available_slots - 1, 0)

    db.session.commit()
    current_app.logger.info("Seeded demo data at %s", datetime.utcnow().isoformat())
    return len(created_treks)


def _register_scheduled_jobs(app: Flask) -> None:
    """Celery beat schedule (daily reminders + monthly report)."""
    from app.tasks import celery_app

    celery_app.conf.update(
        timezone=app.config.get("CELERY_TIMEZONE", "Asia/Kolkata"),
        beat_schedule={
            "daily-trek-reminders": {
                "task": "app.tasks.send_daily_reminders",
                "schedule": crontab_hour(app.config.get("REMINDER_HOUR", 7)),
            },
            "monthly-activity-report": {
                "task": "app.tasks.generate_monthly_report",
                "schedule": crontab_first_day_month(app.config.get("REPORT_HOUR", 8)),
            },
        },
    )


def crontab_hour(hour: int):
    from celery.schedules import crontab

    return crontab(hour=hour, minute=0)


def crontab_first_day_month(hour: int):
    from celery.schedules import crontab

    return crontab(day_of_month="1", hour=hour, minute=0)
