import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, Date, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class EmploymentType(StrEnum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERN = "intern"


class Department(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "departments"
    __table_args__ = (UniqueConstraint("company_id", "name"),)

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(500), default="")
    head_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )


class EmployeeProfile(TimestampMixin, Base):
    """Work information for a staff account.

    Deliberately minimal: no national ID, home address, salary or other
    sensitive personal data. Add fields only with a documented purpose.
    """

    __tablename__ = "employee_profiles"
    __table_args__ = (
        CheckConstraint(
            "employment_type IN ('full_time', 'part_time', 'contract', 'intern')",
            name="employment_type_valid",
        ),
        CheckConstraint(
            "manager_user_id IS NULL OR manager_user_id <> user_id", name="not_own_manager"
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), index=True
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="RESTRICT"), index=True
    )
    job_title: Mapped[str | None] = mapped_column(String(120))
    manager_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    employment_type: Mapped[str] = mapped_column(String(20), default=EmploymentType.FULL_TIME)
    start_date: Mapped[date | None] = mapped_column(Date)


class LeaveRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "leave_requests"
    __table_args__ = (
        CheckConstraint(
            "type IN ('annual', 'sick', 'parental', 'unpaid', 'other')", name="type_valid"
        ),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled')", name="status_valid"
        ),
        CheckConstraint("end_date >= start_date", name="dates_ordered"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(20))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(String(1000), default="")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    decided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    decided_at: Mapped[datetime | None]
    decision_note: Mapped[str | None] = mapped_column(String(1000))


class AttendanceRecord(UUIDPrimaryKeyMixin, Base):
    """Self-reported check-in/out only. No location, device or activity tracking."""

    __tablename__ = "attendance_records"
    __table_args__ = (UniqueConstraint("user_id", "work_date"),)

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    work_date: Mapped[date] = mapped_column(Date)
    check_in_at: Mapped[datetime]
    check_out_at: Mapped[datetime | None]
    note: Mapped[str | None] = mapped_column(String(300))
