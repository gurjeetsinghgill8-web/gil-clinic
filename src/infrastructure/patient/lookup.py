"""Patient lookups that respect merge tombstones (Part F · OPEN-01).

Why this file exists
--------------------
Deduplication merges a duplicate patient into a surviving row and leaves the
old row behind with ``merged_into_patient_id`` set — a tombstone. The rule to
skip tombstones already existed (``NotMergedSpecification``), but the four
presentation-layer **phone** lookups each built their own query and ignored it:

    marketplace_routes · staff_routes · patient_portal_routes · slots_routes

So a booking by phone could resolve to a tombstone. The new visit was then
written against a record the rest of the app treats as deleted, and the
patient's history silently forked in two — the exact class of quiet data bug
that is invisible until somebody reads a chart and finds half the visits.

This module is now the single place those lookups go through, so the rule
cannot be forgotten again.

Design:
  * ``find_by_phone`` returns the most recent **live** patient for a phone
    hash. Returning None means "no live patient" — callers create one.
  * ``follow_merge`` walks a tombstone to its survivor, loop-guarded, so a
    caller holding an old id still lands on the real record.
"""

from __future__ import annotations

import logging
from typing import Any

import sqlalchemy as sa

from src.infrastructure.patient.models.patient_model import PatientModel

logger = logging.getLogger(__name__)

#: A merge chain should be one hop. More than this means a cycle or bad data,
#: and walking further would risk an infinite loop on a hot path.
MAX_MERGE_HOPS = 5


def live_only(stmt: Any) -> Any:
    """Add the tombstone filter to a ``PatientModel`` select.

    Named ``live_only`` rather than ``not_merged`` so the call site reads as
    intent ("only live patients") instead of as a column detail.
    """
    return stmt.where(PatientModel.merged_into_patient_id.is_(None))


async def find_by_phone(
    session: Any,
    phone_hash: str,
    *,
    include_merged: bool = False,
) -> PatientModel | None:
    """Most recent patient for a phone hash, tombstones excluded by default.

    A family sharing one phone number is normal, so this deliberately returns
    the *most recent* live row instead of using ``scalar_one_or_none()`` — the
    latter raised ``MultipleResultsFound`` and turned booking into an HTTP 500
    before BUG-03.
    """
    if not phone_hash:
        return None
    stmt = (
        sa.select(PatientModel)
        .where(PatientModel.phone_hash == phone_hash)
        .order_by(PatientModel.created_at.desc())
        .limit(1)
    )
    if not include_merged:
        stmt = live_only(stmt)
    row = await session.execute(stmt)
    return row.scalars().first()


async def follow_merge(
    session: Any,
    patient: PatientModel | None,
    *,
    max_hops: int = MAX_MERGE_HOPS,
) -> PatientModel | None:
    """If ``patient`` is a tombstone, return the surviving patient instead.

    Loop-guarded: a cycle in the merge graph (bad data, or a half-finished
    merge) returns the last row reached rather than hanging the request.
    """
    seen: set[str] = set()
    current = patient
    hops = 0
    while (
        current is not None
        and current.merged_into_patient_id
        and hops < max_hops
    ):
        target = str(current.merged_into_patient_id)
        if target in seen:
            logger.warning("merge cycle detected at %s — stopping", target)
            break
        seen.add(target)
        row = await session.execute(
            sa.select(PatientModel).where(PatientModel.patient_id == target).limit(1)
        )
        survivor = row.scalars().first()
        if survivor is None:
            # The survivor was deleted too — keep the row we have rather than
            # returning None and losing the patient entirely.
            logger.warning("merge target %s not found", target)
            break
        current = survivor
        hops += 1
    return current


async def find_by_phone_resolved(
    session: Any,
    phone_hash: str,
) -> PatientModel | None:
    """Find by phone and land on the surviving record, never a tombstone.

    The two-step version — used when a merge happened *after* a row was already
    keyed by phone — is why ``follow_merge`` exists rather than trusting the
    filter alone: a tombstone and its survivor can share a phone hash.
    """
    live = await find_by_phone(session, phone_hash)
    if live is not None:
        return live
    # Nothing live under this phone: a tombstone may still hold it.
    stale = await find_by_phone(session, phone_hash, include_merged=True)
    if stale is None:
        return None
    return await follow_merge(session, stale)
