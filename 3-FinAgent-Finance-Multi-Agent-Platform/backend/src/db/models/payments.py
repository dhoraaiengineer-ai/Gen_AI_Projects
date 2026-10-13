"""Customers, accounts and payment transactions (fraud domain). All data is synthetic."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.core.domain import (
    ACCOUNT_STATUSES,
    ACCOUNT_TYPES,
    CHANNELS,
    CURRENCIES,
    FRAUD_TYPES,
    KYC_RISK,
    MERCHANT_CATEGORIES,
)
from src.db.base import Base, TenantScoped, TimestampMixin, in_list
from src.db.models.reference import MONEY


class Customer(TenantScoped, TimestampMixin, Base):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "customer_code"),
        CheckConstraint(in_list("kyc_risk", KYC_RISK), name="kyc_risk"),
        CheckConstraint("customer_code ~ '^CU-[0-9]{6}$'", name="code_format"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    customer_code: Mapped[str] = mapped_column(String(9), nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(160), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32))
    segment: Mapped[str] = mapped_column(String(20), nullable=False)
    home_country: Mapped[str] = mapped_column(String(2), nullable=False)
    home_city: Mapped[str] = mapped_column(String(60), nullable=False)
    kyc_risk: Mapped[str] = mapped_column(String(6), nullable=False, default="low")
    date_of_birth: Mapped[date | None] = mapped_column(Date)


class Account(TenantScoped, TimestampMixin, Base):
    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "account_number"),
        CheckConstraint(in_list("account_type", ACCOUNT_TYPES), name="account_type"),
        CheckConstraint(in_list("status", ACCOUNT_STATUSES), name="status"),
        CheckConstraint(in_list("currency", CURRENCIES), name="currency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    account_number: Mapped[str] = mapped_column(String(20), nullable=False)
    account_type: Mapped[str] = mapped_column(String(10), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    balance: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(8), nullable=False, default="active")
    opened_at: Mapped[date] = mapped_column(Date, nullable=False)


class Transaction(TenantScoped, Base):
    """Payment transaction. ``is_fraud``/``fraud_type`` are synthetic training labels."""

    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "transaction_ref"),
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint(in_list("currency", CURRENCIES), name="currency"),
        CheckConstraint(in_list("channel", CHANNELS), name="channel"),
        CheckConstraint(
            in_list("merchant_category", MERCHANT_CATEGORIES), name="merchant_category"
        ),
        CheckConstraint(
            f"fraud_type IS NULL OR {in_list('fraud_type', FRAUD_TYPES)}", name="fraud_type"
        ),
        CheckConstraint("transaction_ref ~ '^TX-[0-9]{6,9}$'", name="ref_format"),
        Index("ix_transactions_account_ts", "account_id", "ts"),
        Index("ix_transactions_ts", "ts"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    transaction_ref: Mapped[str] = mapped_column(String(12), nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    merchant: Mapped[str] = mapped_column(String(80), nullable=False)
    merchant_category: Mapped[str] = mapped_column(String(20), nullable=False)
    channel: Mapped[str] = mapped_column(String(10), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    city: Mapped[str] = mapped_column(String(60), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    device_id: Mapped[str] = mapped_column(String(40), nullable=False)
    is_new_device: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_fraud: Mapped[bool | None] = mapped_column(Boolean)
    fraud_type: Mapped[str | None] = mapped_column(String(20))
