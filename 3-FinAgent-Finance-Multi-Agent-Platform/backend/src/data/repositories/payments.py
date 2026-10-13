"""Customers, accounts and payment transactions (read-only). PII is masked at this boundary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import Float, Select, cast, func, select

from src.db.models import Account, Customer, FraudPrediction, Transaction
from src.db.session import Database
from src.ml.features.fraud import LOOKBACK_DAYS, TxRecord
from src.security.pii import mask_account_number, mask_email, mask_name, mask_phone


@dataclass(frozen=True)
class CustomerProfile:
    customer_code: str
    name: str  # masked
    email: str  # masked
    phone: str | None  # masked
    segment: str
    home_country: str
    home_city: str
    kyc_risk: str
    accounts: list[dict[str, Any]]


@dataclass(frozen=True)
class TransactionRow:
    transaction_ref: str
    account: str  # masked account number
    customer_code: str
    ts: datetime
    amount: float
    currency: str
    merchant: str
    merchant_category: str
    channel: str
    country: str
    city: str
    device_id: str
    is_new_device: bool
    account_opened: date


class PaymentsRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def customer_profile(self, customer_code: str) -> CustomerProfile | None:
        async with self.db.sessions() as session:
            customer = await session.scalar(
                select(Customer).where(Customer.customer_code == customer_code)
            )
            if customer is None:
                return None
            accounts = list(
                await session.scalars(select(Account).where(Account.customer_id == customer.id))
            )
        return CustomerProfile(
            customer.customer_code,
            mask_name(customer.full_name),
            mask_email(customer.email),
            mask_phone(customer.phone) if customer.phone else None,
            customer.segment,
            customer.home_country,
            customer.home_city,
            customer.kyc_risk,
            [
                {
                    "account": mask_account_number(a.account_number),
                    "type": a.account_type,
                    "currency": a.currency,
                    "balance": float(a.balance),
                    "status": a.status,
                    "openedAt": a.opened_at.isoformat(),
                }
                for a in accounts
            ],
        )

    def _tx_select(self) -> Select[Any]:
        return (
            select(
                Transaction.transaction_ref.label("ref"),
                Account.account_number.label("account_number"),
                Customer.customer_code.label("customer_code"),
                Transaction.ts.label("ts"),
                cast(Transaction.amount, Float).label("amount"),
                Transaction.currency.label("currency"),
                Transaction.merchant.label("merchant"),
                Transaction.merchant_category.label("merchant_category"),
                Transaction.channel.label("channel"),
                Transaction.country.label("country"),
                Transaction.city.label("city"),
                Transaction.device_id.label("device_id"),
                Transaction.is_new_device.label("is_new_device"),
                Account.opened_at.label("opened_at"),
            )
            .join(Account, Account.id == Transaction.account_id)
            .join(Customer, Customer.id == Account.customer_id)
        )

    @staticmethod
    def _row(r: Any) -> TransactionRow:
        return TransactionRow(
            r.ref,
            mask_account_number(r.account_number),
            r.customer_code,
            r.ts,
            r.amount,
            r.currency,
            r.merchant,
            r.merchant_category,
            r.channel,
            r.country,
            r.city,
            r.device_id,
            r.is_new_device,
            r.opened_at,
        )

    async def transactions(
        self,
        *,
        customer_code: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        min_amount: float | None = None,
        limit: int = 200,
    ) -> list[TransactionRow]:
        stmt = self._tx_select()
        if customer_code:
            stmt = stmt.where(Customer.customer_code == customer_code)
        if since:
            stmt = stmt.where(Transaction.ts >= since)
        if until:
            stmt = stmt.where(Transaction.ts <= until)
        if min_amount is not None:
            stmt = stmt.where(Transaction.amount >= min_amount)
        stmt = stmt.order_by(Transaction.ts.desc()).limit(limit)
        async with self.db.sessions() as session:
            return [self._row(r) for r in (await session.execute(stmt)).all()]

    async def transaction(self, ref: str) -> TransactionRow | None:
        async with self.db.sessions() as session:
            row = (
                await session.execute(self._tx_select().where(Transaction.transaction_ref == ref))
            ).first()
        return self._row(row) if row else None

    async def latest_transaction_time(self) -> datetime | None:
        async with self.db.sessions() as session:
            return await session.scalar(select(func.max(Transaction.ts).label("ts")))

    async def fraud_records(
        self,
        *,
        customer_code: str | None = None,
        transaction_ref: str | None = None,
        days: int = 30,
    ) -> tuple[list[TxRecord], set[str]]:
        """Records for fraud scoring plus the refs to score.

        Includes each account's preceding ``LOOKBACK_DAYS`` of history so features match training.
        """
        stmt = (
            select(
                Transaction.transaction_ref.label("ref"),
                Transaction.account_id.label("account_id"),
                Transaction.ts.label("ts"),
                cast(Transaction.amount, Float).label("amount"),
                Transaction.merchant_category.label("category"),
                Transaction.channel.label("channel"),
                Transaction.country.label("country"),
                Transaction.latitude.label("latitude"),
                Transaction.longitude.label("longitude"),
                Transaction.device_id.label("device"),
                Transaction.is_new_device.label("is_new_device"),
                Customer.home_country.label("home_country"),
                Account.opened_at.label("opened_at"),
            )
            .join(Account, Account.id == Transaction.account_id)
            .join(Customer, Customer.id == Account.customer_id)
        )
        async with self.db.sessions() as session:
            if transaction_ref:
                anchor = (
                    await session.execute(
                        select(Transaction.account_id.label("a"), Transaction.ts.label("ts")).where(
                            Transaction.transaction_ref == transaction_ref
                        )
                    )
                ).first()
                if anchor is None:
                    return [], set()
                stmt = stmt.where(
                    Transaction.account_id == anchor.a,
                    Transaction.ts >= anchor.ts - timedelta(days=LOOKBACK_DAYS),
                    Transaction.ts <= anchor.ts,
                )
            elif customer_code:
                latest = await session.scalar(
                    select(func.max(Transaction.ts).label("ts"))
                    .join(Account, Account.id == Transaction.account_id)
                    .join(Customer, Customer.id == Account.customer_id)
                    .where(Customer.customer_code == customer_code)
                )
                if latest is None:
                    return [], set()
                start = latest - timedelta(days=days)
                stmt = stmt.where(
                    Customer.customer_code == customer_code,
                    Transaction.ts >= start - timedelta(days=LOOKBACK_DAYS),
                )
            else:
                raise ValueError("customer_code or transaction_ref is required")
            rows = (await session.execute(stmt.order_by(Transaction.ts).limit(5_000))).all()
        records = [
            TxRecord(
                r.ref,
                str(r.account_id),
                r.ts,
                r.amount,
                r.category,
                r.channel,
                r.country,
                r.latitude,
                r.longitude,
                r.device,
                r.is_new_device,
                r.home_country,
                r.opened_at,
            )
            for r in rows
        ]
        if transaction_ref:
            return records, {transaction_ref}
        return records, {r.ref for r in records if r.ts >= start}


async def recent_fraud_alerts(db: Database, limit: int = 25) -> list[dict[str, Any]]:
    """Latest model score per transaction, highest probability first (persisted predictions)."""
    latest = (
        select(
            FraudPrediction.transaction_id.label("tx_id"),
            func.max(FraudPrediction.id).label("pred_id"),
        )
        .group_by(FraudPrediction.transaction_id)
        .subquery()
    )
    stmt = (
        select(
            Transaction.transaction_ref.label("ref"),
            Transaction.ts.label("ts"),
            cast(Transaction.amount, Float).label("amount"),
            Transaction.currency.label("currency"),
            Transaction.merchant_category.label("category"),
            Transaction.channel.label("channel"),
            Transaction.country.label("country"),
            FraudPrediction.probability.label("probability"),
            FraudPrediction.risk_level.label("risk_level"),
            FraudPrediction.reason_codes.label("reasons"),
            FraudPrediction.model_version.label("model_version"),
            FraudPrediction.created_at.label("scored_at"),
        )
        .join(latest, latest.c.pred_id == FraudPrediction.id)
        .join(Transaction, Transaction.id == FraudPrediction.transaction_id)
        .order_by(FraudPrediction.probability.desc())
        .limit(limit)
    )
    async with db.sessions() as session:
        rows = (await session.execute(stmt)).all()
    return [
        {
            "transactionId": r.ref,
            "at": r.ts,
            "amount": round(float(r.amount), 2),
            "currency": r.currency,
            "category": r.category,
            "channel": r.channel,
            "country": r.country,
            "probability": round(float(r.probability), 4),
            "riskLevel": r.risk_level,
            "reasons": list(r.reasons or [])[:5],
            "modelVersion": r.model_version,
            "scoredAt": r.scored_at,
        }
        for r in rows
    ]
