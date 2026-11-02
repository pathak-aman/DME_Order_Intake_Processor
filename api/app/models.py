from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    orders: Mapped[List["Order"]] = relationship("Order", back_populates="owner", cascade="all, delete-orphan")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Extracted clinical fields — nullable because extraction may yield null
    patient_first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    patient_last_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    patient_dob: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # stored as ISO date string
    provider_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    provider_npi: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    # Status: "verified" | "needs_review"
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="needs_review")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    owner: Mapped["User"] = relationship("User", back_populates="orders")
