"""Database models for the Trekking Management Application.

The database is created programmatically from these models (``db.create_all()``);
manual DB creation is not used anywhere in this project.

Unified user model: a single ``User`` table differentiates the three roles
(admin / staff / trekker) via the ``role`` column, as required by the spec.
"""
from datetime import datetime, date

from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db

ROLE_ADMIN = "admin"
ROLE_STAFF = "staff"
ROLE_USER = "user"
ROLES = (ROLE_ADMIN, ROLE_STAFF, ROLE_USER)

TREK_PENDING = "Pending"
TREK_APPROVED = "Approved"
TREK_OPEN = "Open"
TREK_CLOSED = "Closed"
TREK_COMPLETED = "Completed"
TREK_STATUSES = (TREK_PENDING, TREK_APPROVED, TREK_OPEN, TREK_CLOSED, TREK_COMPLETED)

DIFFICULTIES = ("Easy", "Moderate", "Hard")

BOOKING_BOOKED = "Booked"
BOOKING_CANCELLED = "Cancelled"
BOOKING_COMPLETED = "Completed"
BOOKING_STATUSES = (BOOKING_BOOKED, BOOKING_CANCELLED, BOOKING_COMPLETED)

USER_ACTIVE = "Active"
USER_DEACTIVATED = "Deactivated"
USER_BLACKLISTED = "Blacklisted"
USER_STATUSES = (USER_ACTIVE, USER_DEACTIVATED, USER_BLACKLISTED)


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class User(TimestampMixin, db.Model):
    """Unified account model for Admin, Trek Staff and Trekkers."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20))
    password_hash = db.Column(db.String(255), nullable=False)

    role = db.Column(db.String(10), nullable=False, default=ROLE_USER, index=True)
    status = db.Column(db.String(15), nullable=False, default=USER_ACTIVE, index=True)

    # Staff-only attributes
    specialization = db.Column(db.String(80))
    contact_details = db.Column(db.String(200))

    bookings = db.relationship(
        "Booking", back_populates="user", lazy="dynamic", cascade="all, delete-orphan"
    )
    # staff_assignments has two FKs into ``users`` (staff_id + assigned_by),
    # so foreign_keys must be stated explicitly or SQLAlchemy cannot resolve the join.
    assignments = db.relationship(
        "StaffAssignment",
        back_populates="staff",
        foreign_keys="StaffAssignment.staff_id",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    @property
    def is_active_account(self) -> bool:
        return self.status == USER_ACTIVE

    def to_dict(self, include_private: bool = False) -> dict:
        data = {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "phone": self.phone,
            "role": self.role,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if self.role == ROLE_STAFF:
            data["specialization"] = self.specialization
            data["contact_details"] = self.contact_details
        if include_private:
            data["updated_at"] = self.updated_at.isoformat() if self.updated_at else None
        return data


trek_staff_assoc = db.Table(
    "trek_assigned_staff",
    db.Column("trek_id", db.Integer, db.ForeignKey("treks.id", ondelete="CASCADE"), primary_key=True),
    db.Column("staff_id", db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
)


class Trek(TimestampMixin, db.Model):
    """A trekking route/event managed by admin and coordinated by assigned staff."""

    __tablename__ = "treks"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, index=True)
    location = db.Column(db.String(120), nullable=False, index=True)
    region = db.Column(db.String(80))
    difficulty = db.Column(db.String(12), nullable=False, default="Easy")
    duration_days = db.Column(db.Integer, nullable=False, default=1)
    total_slots = db.Column(db.Integer, nullable=False, default=10)
    available_slots = db.Column(db.Integer, nullable=False, default=10)
    assigned_staff_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    status = db.Column(db.String(12), nullable=False, default=TREK_PENDING, index=True)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    base_price = db.Column(db.Float, nullable=False, default=0.0)
    min_age = db.Column(db.Integer, nullable=False, default=10)
    description = db.Column(db.Text)
    instructions = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    assigned_staff = db.relationship(
        "User", foreign_keys=[assigned_staff_id], back_populates="treks", lazy="joined"
    )
    creator = db.relationship("User", foreign_keys=[created_by], lazy="joined")
    bookings = db.relationship(
        "Booking", back_populates="trek", lazy="dynamic", cascade="all, delete-orphan"
    )
    support_staff = db.relationship(
        "User", secondary=trek_staff_assoc, backref="supporting_treks", lazy="subquery"
    )
    assignments = db.relationship(
        "StaffAssignment",
        back_populates="trek",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def booked_count(self) -> int:
        return self.bookings.filter_by(status=BOOKING_BOOKED).count()

    def can_be_booked(self) -> bool:
        return self.status == TREK_OPEN and self.available_slots > 0

    def to_dict(self, include_stats: bool = True) -> dict:
        data = {
            "id": self.id,
            "trek_id": f"TRK{self.id:04d}",
            "name": self.name,
            "location": self.location,
            "region": self.region,
            "difficulty": self.difficulty,
            "duration_days": self.duration_days,
            "total_slots": self.total_slots,
            "available_slots": self.available_slots,
            "assigned_staff_id": self.assigned_staff_id,
            "assigned_staff_name": self.assigned_staff.full_name if self.assigned_staff else None,
            "status": self.status,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "base_price": self.base_price,
            "min_age": self.min_age,
            "description": self.description,
            "instructions": self.instructions,
            "support_staff": [s.id for s in self.support_staff],
        }
        if include_stats:
            data["booked_count"] = self.booked_count
        return data


class StaffAssignment(db.Model):
    """Explicit assignment record of a staff member to a trek (audit friendly)."""

    __tablename__ = "staff_assignments"

    id = db.Column(db.Integer, primary_key=True)
    trek_id = db.Column(db.Integer, db.ForeignKey("treks.id", ondelete="CASCADE"), nullable=False)
    staff_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    assigned_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    role_label = db.Column(db.String(40), default="Lead")

    # ``treks`` has no other FK from staff_assignments, so the join is unambiguous.
    trek = db.relationship("Trek", back_populates="assignments")
    # ``users`` is reachable via two FKs (staff_id, assigned_by) -> state foreign_keys.
    staff = db.relationship(
        "User",
        foreign_keys=[staff_id],
        back_populates="assignments",
    )
    assigned_by_user = db.relationship("User", foreign_keys=[assigned_by])

    __table_args__ = (db.UniqueConstraint("trek_id", "staff_id", name="uq_trek_staff"),)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "trek_id": self.trek_id,
            "staff_id": self.staff_id,
            "staff_name": self.staff.full_name if self.staff else None,
            "trek_name": self.trek.name if self.trek else None,
            "role_label": self.role_label,
            "assigned_at": self.assigned_at.isoformat() if self.assigned_at else None,
        }


# Back-reference configured after both classes exist.
User.treks = db.relationship(
    "Trek",
    foreign_keys=[Trek.assigned_staff_id],
    back_populates="assigned_staff",
    lazy="dynamic",
)


class Booking(TimestampMixin, db.Model):
    """A trekker's booking for a trek."""

    __tablename__ = "bookings"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    trek_id = db.Column(db.Integer, db.ForeignKey("treks.id", ondelete="CASCADE"), nullable=False, index=True)
    booking_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    status = db.Column(db.String(12), nullable=False, default=BOOKING_BOOKED, index=True)
    payment_status = db.Column(db.String(15), nullable=False, default="Pending")
    amount = db.Column(db.Float, nullable=False, default=0.0)
    participants = db.Column(db.Integer, nullable=False, default=1)
    notes = db.Column(db.Text)
    cancelled_at = db.Column(db.DateTime)

    user = db.relationship("User", back_populates="bookings", lazy="joined")
    trek = db.relationship("Trek", back_populates="bookings", lazy="joined")

    __table_args__ = (
        # Prevent duplicate active bookings for the same user & trek.
        db.Index("uq_active_booking_per_user_trek", "user_id", "trek_id", unique=True),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "booking_id": f"BKG{self.id:05d}",
            "user_id": self.user_id,
            "user_name": self.user.full_name if self.user else None,
            "user_email": self.user.email if self.user else None,
            "trek_id": self.trek_id,
            "trek_name": self.trek.name if self.trek else None,
            "trek_location": self.trek.location if self.trek else None,
            "trek_start_date": self.trek.start_date.isoformat() if self.trek and self.trek.start_date else None,
            "trek_end_date": self.trek.end_date.isoformat() if self.trek and self.trek.end_date else None,
            "trek_difficulty": self.trek.difficulty if self.trek else None,
            "trek_duration_days": self.trek.duration_days if self.trek else None,
            "booking_date": self.booking_date.isoformat() if self.booking_date else None,
            "status": self.status,
            "payment_status": self.payment_status,
            "amount": self.amount,
            "participants": self.participants,
            "notes": self.notes,
            "cancelled_at": self.cancelled_at.isoformat() if self.cancelled_at else None,
        }


class Notification(db.Model):
    """In-app notification (booking confirmations, cancellations, job alerts)."""

    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(30), default="general")
    read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", backref=db.backref("notifications", lazy="dynamic"))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "message": self.message,
            "category": self.category,
            "read": self.read,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class JobRun(db.Model):
    """Tracks background/scheduled job executions for visibility in the UI."""

    __tablename__ = "job_runs"

    id = db.Column(db.Integer, primary_key=True)
    job_name = db.Column(db.String(80), nullable=False)
    status = db.Column(db.String(20), default="started")  # started/success/failed
    detail = db.Column(db.Text)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    finished_at = db.Column(db.DateTime)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "job_name": self.job_name,
            "status": self.status,
            "detail": self.detail,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }


def today() -> date:  # pragma: no cover - convenience helper
    return date.today()
