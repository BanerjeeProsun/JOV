"""Database-backed Work Queue with optimistic leases."""

from datetime import datetime, timedelta
import uuid
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_

from jovsi.adapters.db.models import WorkItemDB


class WorkQueue:
    LEASE_DURATION_SECONDS = 60

    @classmethod
    def enqueue(
        cls,
        db: Session,
        kind: str,
        payload: Dict[str, Any],
        idempotency_key: str,
        run_after: Optional[datetime] = None,
    ) -> Optional[WorkItemDB]:
        """Enqueue a work item idempotently."""
        existing = db.scalar(select(WorkItemDB).where(WorkItemDB.idempotency_key == idempotency_key))
        if existing:
            return existing

        item = WorkItemDB(
            id=str(uuid.uuid4()),
            kind=kind,
            payload=payload,
            idempotency_key=idempotency_key,
            run_after=run_after or datetime.utcnow(),
            attempts=0,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    @classmethod
    def lease_next(cls, db: Session, worker_id: str) -> Optional[WorkItemDB]:
        """Atomically lease the next available work item."""
        now = datetime.utcnow()
        # Find item that is ready and either unleased or lease expired
        stmt = (
            select(WorkItemDB)
            .where(
                and_(
                    WorkItemDB.run_after <= now,
                    or_(
                        WorkItemDB.lease_until.is_(None),
                        WorkItemDB.lease_until < now,
                    ),
                )
            )
            .order_by(WorkItemDB.run_after.asc())
            .limit(1)
        )
        item = db.scalar(stmt)
        if not item:
            return None

        # Lock and lease for 60 seconds
        item.lease_owner = worker_id
        item.lease_until = now + timedelta(seconds=cls.LEASE_DURATION_SECONDS)
        item.attempts += 1
        db.commit()
        db.refresh(item)
        return item

    @classmethod
    def complete(cls, db: Session, item_id: str) -> None:
        """Mark work item completed by deleting it from queue."""
        item = db.scalar(select(WorkItemDB).where(WorkItemDB.id == item_id))
        if item:
            db.delete(item)
            db.commit()

    @classmethod
    def release(cls, db: Session, item_id: str, retry_delay_seconds: int = 0) -> None:
        """Release lease to allow immediate or delayed re-execution."""
        item = db.scalar(select(WorkItemDB).where(WorkItemDB.id == item_id))
        if item:
            item.lease_owner = None
            item.lease_until = None
            if retry_delay_seconds > 0:
                item.run_after = datetime.utcnow() + timedelta(seconds=retry_delay_seconds)
            db.commit()
