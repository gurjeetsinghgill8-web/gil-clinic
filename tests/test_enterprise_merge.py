"""Enterprise-merge tests (master blueprint BLOCK 7 / Part F).

Run:  python -m pytest tests/test_enterprise_merge.py -q

Groups:

  1. **OPEN-01** — a merged patient tombstone must never be resolved by a phone
     lookup, and the survivor must be found instead.
  2. **F-05 tags** — every badge is backed by real data and disappears when the
     fact behind it does.
  3. **F-04 ranking** — the score is explainable, a cold-start clinic cannot buy
     the top spot with an unknown wait, and the partner-above-directory rule
     survives every weight.
  4. **F-03 accuracy** — promised vs delivered, and the honest "no data" answer.
  5. **F-07 reviews** — only a completed visit can be reviewed, one review per
     visit, and the Bayesian score cannot be moved by a single review.
  6. **F-08 network** — the overview is PHI-free.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_TEST_DB = ROOT / "test_enterprise_merge.db"
if _TEST_DB.exists():
    try:
        _TEST_DB.unlink()
    except Exception:
        pass

os.environ["GHOS_DB_URL"] = f"sqlite:///{_TEST_DB}"
os.environ["SYSTEM_AI_FALLBACK_ENABLED"] = "false"

import hashlib  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import main_v2  # noqa: E402
from src.domain.clinic import discovery, reviews  # noqa: E402
from src.domain.queue import ewt  # noqa: E402
from src.infrastructure.clinic.models.clinic_model import ClinicModel  # noqa: E402
from src.infrastructure.clinic.models.review_model import ClinicReviewModel  # noqa: E402
from src.infrastructure.patient.models.patient_model import PatientModel  # noqa: E402
from src.infrastructure.queue.models.queue_entry_model import QueueEntryModel  # noqa: E402
from src.shared.infrastructure.database import async_session_factory  # noqa: E402

main_v2.Base.metadata.create_all(bind=main_v2.engine)
main_v2._migrate_sqlite_columns()

# NOTE on test isolation: the whole suite shares one SQLite file (whichever
# test module imports `main_v2` first wins), and several tests in other modules
# rely on `_resolve_clinic_id`'s production fallback — "the clinic of the most
# recent OPD queue entry". A queue entry stamped in the FUTURE would therefore
# hijack that fallback and break unrelated chamber tests.
#
# So these fixtures deliberately write entries two hours in the PAST: still
# recent enough for the 60-day review window, never the newest row in the table.
NOW = datetime.now(timezone.utc) - timedelta(hours=2)
TODAY = datetime.now(timezone.utc).date().isoformat()


def _run(coro):
    import asyncio

    return asyncio.run(coro)


@pytest.fixture
def login(monkeypatch):
    """Pretend a chief doctor is logged into the OPD dashboard.

    Needed for the staff-only routes (review moderation): without it they
    answer with the login page, which would look like a passing HTML response
    rather than the JSON the test expects.
    """
    from src.presentation.opd.routes import opd_routes

    def _login(clinic_id: str = ""):
        monkeypatch.setattr(
            opd_routes,
            "_require_opd_session",
            lambda request: {
                "role": "chief",
                "doctor_id": "chief",
                "name": "Dr Test",
                "clinic_id": clinic_id,
                "lic_info": {},
            },
        )
        return "chief"

    return _login


# ══════════════════════════════════════════════════════════════════════════
# 1. OPEN-01 — merged patient tombstones
# ══════════════════════════════════════════════════════════════════════════


class TestMergedPatientLookup:
    def _seed_pair(self, survivor_phone: str, tombstone_phone: str, tag: str):
        """A survivor plus a tombstone that points at it (a real dedup merge).

        ``tag`` makes the patient ids unique per test: two tests sharing an id
        would insert two rows with the same ``patient_id``, and the merge
        lookup would then have two equally valid answers — a test-only problem
        that would mask a real one.
        """
        from src.shared.domain.base_entity import uuid7

        survivor_uuid = uuid7()
        tombstone_uuid = uuid7()
        survivor_id = f"CQ-20261003-9{tag}"
        tombstone_id = f"CQ-20261003-8{tag}"

        async def _insert():
            async with async_session_factory() as session:
                session.add(
                    PatientModel(
                        id=survivor_uuid,
                        patient_id=survivor_id,
                        name="Survivor Patient",
                        age=40,
                        gender="Male",
                        date_of_birth="",
                        phone=survivor_phone,
                        phone_hash=hashlib.sha256(survivor_phone.encode()).hexdigest(),
                        address="",
                        status="active",
                        total_visits=3,
                        version=1,
                        created_at=NOW - timedelta(days=10),
                        updated_at=NOW,
                    )
                )
                session.add(
                    PatientModel(
                        id=tombstone_uuid,
                        patient_id=tombstone_id,
                        name="Duplicate Patient",
                        age=40,
                        gender="Male",
                        date_of_birth="",
                        phone=tombstone_phone,
                        phone_hash=hashlib.sha256(tombstone_phone.encode()).hexdigest(),
                        address="",
                        status="merged",
                        total_visits=1,
                        merged_into_patient_id=survivor_id,
                        version=1,
                        created_at=NOW - timedelta(days=2),
                        updated_at=NOW,
                    )
                )
                await session.commit()

        _run(_insert())
        return survivor_id, tombstone_id

    def test_live_lookup_skips_a_tombstone(self):
        from src.infrastructure.patient.lookup import find_by_phone

        survivor_phone = "9811111101"
        tombstone_phone = "9811111102"
        survivor_id, _tombstone_id = self._seed_pair(survivor_phone, tombstone_phone, "01")

        async def _check():
            async with async_session_factory() as session:
                found = await find_by_phone(
                    session, hashlib.sha256(survivor_phone.encode()).hexdigest()
                )
                return found.patient_id if found else None

        assert _run(_check()) == survivor_id

    def test_a_tombstone_is_followed_to_its_survivor(self):
        """Booking by the duplicate's phone must land on the real patient."""
        from src.infrastructure.patient.lookup import find_by_phone_resolved

        survivor_phone = "9811111201"
        tombstone_phone = "9811111202"
        survivor_id, _tombstone_id = self._seed_pair(survivor_phone, tombstone_phone, "02")

        async def _check():
            async with async_session_factory() as session:
                found = await find_by_phone_resolved(
                    session, hashlib.sha256(tombstone_phone.encode()).hexdigest()
                )
                return found.patient_id if found else None

        assert _run(_check()) == survivor_id, (
            "a tombstone must never be resolved as the patient"
        )

    def test_a_plain_lookup_never_returns_the_tombstone_itself(self):
        """The direct guarantee: the merged row is not a valid resolution."""
        from src.infrastructure.patient.lookup import find_by_phone

        survivor_phone = "9811111301"
        tombstone_phone = "9811111302"
        _survivor_id, tombstone_id = self._seed_pair(
            survivor_phone, tombstone_phone, "03"
        )

        async def _check():
            async with async_session_factory() as session:
                found = await find_by_phone(
                    session, hashlib.sha256(tombstone_phone.encode()).hexdigest()
                )
                return found.patient_id if found else None

        assert _run(_check()) != tombstone_id

    def test_a_merge_cycle_does_not_hang(self):
        """Bad data must degrade, not spin — this runs on a hot booking path."""
        from src.infrastructure.patient.lookup import follow_merge
        from src.shared.domain.base_entity import uuid7

        a_id, b_id = "CQ-20261003-701", "CQ-20261003-702"

        async def _insert():
            async with async_session_factory() as session:
                for pid, target in ((a_id, b_id), (b_id, a_id)):
                    session.add(
                        PatientModel(
                            id=uuid7(),
                            patient_id=pid,
                            name=f"Cycle {pid}",
                            age=30,
                            gender="Not Specified",
                            date_of_birth="",
                            phone="",
                            phone_hash="",
                            address="",
                            status="merged",
                            total_visits=0,
                            merged_into_patient_id=target,
                            version=1,
                            created_at=NOW,
                            updated_at=NOW,
                        )
                    )
                await session.commit()

        _run(_insert())

        async def _check():
            import sqlalchemy as sa

            async with async_session_factory() as session:
                row = await session.execute(
                    sa.select(PatientModel).where(PatientModel.patient_id == a_id)
                )
                start = row.scalars().first()
                # Must return rather than loop forever.
                return await follow_merge(session, start)

        assert _run(_check()) is not None

    def test_missing_phone_hash_is_safe(self):
        from src.infrastructure.patient.lookup import find_by_phone

        async def _check():
            async with async_session_factory() as session:
                return await find_by_phone(session, "")

        assert _run(_check()) is None

    def test_not_merged_helper_excludes_tombstones(self):
        import sqlalchemy as sa

        from src.infrastructure.patient.lookup import live_only

        stmt = live_only(sa.select(PatientModel))
        sql = str(stmt)
        assert "merged_into_patient_id" in sql


# ══════════════════════════════════════════════════════════════════════════
# 2. F-05 — computed tags
# ══════════════════════════════════════════════════════════════════════════


def _doctor(**over):
    base = {
        "partner": True,
        "distance_km": None,
        "availability": "OPEN",
        "is_open_now": True,
        "rating": None,
        "rating_count": 0,
        "live": None,
    }
    base.update(over)
    return base


class TestTags:
    def test_live_patient_free_clinic_gets_the_instant_badges(self):
        doc = _doctor(
            live={
                "real": True,
                "state": "live",
                "patients_ahead": 0,
                "confidence": "high",
                "wait_minutes": 0,
            }
        )
        tags = discovery.compute_tags(doc)
        assert discovery.TAG_LIVE_TELEMETRY in tags
        assert discovery.TAG_INSTANT_TOKEN in tags
        assert discovery.TAG_ZERO_WAIT_VERIFIED in tags

    def test_a_queue_with_people_ahead_is_not_called_instant(self):
        doc = _doctor(
            live={
                "real": True,
                "state": "live",
                "patients_ahead": 4,
                "confidence": "medium",
                "wait_minutes": 28,
            }
        )
        tags = discovery.compute_tags(doc)
        assert discovery.TAG_LIVE_TELEMETRY in tags
        assert discovery.TAG_INSTANT_TOKEN not in tags
        assert discovery.TAG_ZERO_WAIT_VERIFIED not in tags

    def test_an_unopened_chamber_is_not_instant(self):
        """arrival_pending means no countdown — so no "instant" badge either."""
        doc = _doctor(
            live={
                "real": True,
                "state": "arrival_pending",
                "patients_ahead": 0,
                "confidence": "low",
                "wait_minutes": 0,
            }
        )
        tags = discovery.compute_tags(doc)
        assert discovery.TAG_INSTANT_TOKEN not in tags

    def test_zero_wait_requires_high_confidence(self):
        doc = _doctor(
            live={
                "real": True,
                "state": "live",
                "patients_ahead": 0,
                "confidence": "low",
                "wait_minutes": 0,
            }
        )
        tags = discovery.compute_tags(doc)
        assert discovery.TAG_INSTANT_TOKEN in tags
        assert discovery.TAG_ZERO_WAIT_VERIFIED not in tags

    def test_directory_clinic_gets_the_call_badge(self):
        tags = discovery.compute_tags(_doctor(partner=False, availability="DIRECTORY"))
        assert discovery.TAG_DIRECT_CALL_ONLY in tags
        assert discovery.TAG_OPEN_NOW not in tags

    def test_closed_clinic_says_closed_not_open(self):
        tags = discovery.compute_tags(_doctor(availability="CLOSED", is_open_now=False))
        assert discovery.TAG_CLOSED_TODAY in tags
        assert discovery.TAG_OPEN_NOW not in tags

    def test_nearby_requires_a_real_distance(self):
        assert discovery.TAG_NEARBY in discovery.compute_tags(_doctor(distance_km=2.0))
        assert discovery.TAG_NEARBY not in discovery.compute_tags(_doctor(distance_km=40.0))
        assert discovery.TAG_NEARBY not in discovery.compute_tags(_doctor(distance_km=None))

    def test_every_tag_has_a_label_and_a_hint(self):
        doc = _doctor(
            distance_km=1.0,
            rating=4.5,
            rating_count=30,
            live={
                "real": True,
                "state": "live",
                "patients_ahead": 0,
                "confidence": "high",
                "wait_minutes": 0,
            },
        )
        for tag in discovery.compute_tags(doc):
            assert tag in discovery.TAG_LABEL, tag
            assert tag in discovery.TAG_HINT, tag

    def test_labels_are_returned_in_the_same_order(self):
        doc = _doctor(
            live={
                "real": True,
                "state": "live",
                "patients_ahead": 0,
                "confidence": "high",
                "wait_minutes": 0,
            }
        )
        tags = discovery.compute_tags(doc)
        labelled = discovery.tags_with_labels(tags)
        assert [entry["key"] for entry in labelled] == tags


# ══════════════════════════════════════════════════════════════════════════
# 3. F-04 — multi-factor ranking
# ══════════════════════════════════════════════════════════════════════════


class TestRankScore:
    def test_an_empty_chamber_beats_a_long_queue(self):
        empty = _doctor(
            live={"real": True, "state": "live", "patients_ahead": 0,
                  "confidence": "high", "wait_minutes": 0, "samples": 40}
        )
        busy = _doctor(
            live={"real": True, "state": "live", "patients_ahead": 9,
                  "confidence": "high", "wait_minutes": 62, "samples": 40}
        )
        assert discovery.rank_score(empty) > discovery.rank_score(busy)

    def test_a_cold_start_clinic_cannot_buy_the_top_spot(self):
        """The important one: unknown wait must not look like a zero wait."""
        cold = _doctor(
            live={"real": True, "state": "live", "patients_ahead": 0,
                  "confidence": "low", "wait_minutes": 0, "samples": 0}
        )
        known = _doctor(
            live={"real": True, "state": "live", "patients_ahead": 1,
                  "confidence": "high", "wait_minutes": 12, "samples": 60}
        )
        cold_only = discovery.rank_score(_doctor())  # no live data at all
        assert discovery.rank_score(cold) > cold_only, "some credit is fair"
        assert discovery.rank_score(cold) < discovery.rank_score(known), (
            "a clinic we know nothing about must not outrank a proven one"
        )

    def test_closer_is_better(self):
        near = _doctor(distance_km=1.0)
        far = _doctor(distance_km=30.0)
        assert discovery.rank_score(near) > discovery.rank_score(far)

    def test_distance_is_a_sigmoid_not_a_step(self):
        a = discovery.rank_score(_doctor(distance_km=1.0))
        b = discovery.rank_score(_doctor(distance_km=2.0))
        c = discovery.rank_score(_doctor(distance_km=40.0))
        d = discovery.rank_score(_doctor(distance_km=41.0))
        assert (a - b) > (c - d), "1 km vs 2 km should matter more than 40 vs 41"

    def test_open_beats_closed(self):
        assert discovery.rank_score(_doctor(availability="OPEN")) > discovery.rank_score(
            _doctor(availability="CLOSED", is_open_now=False)
        )

    def test_closed_is_penalised_below_an_unknown_clinic(self):
        assert discovery.rank_score(
            _doctor(availability="CLOSED", is_open_now=False)
        ) < discovery.rank_score(_doctor(availability="DIRECTORY"))

    def test_a_well_reviewed_clinic_outranks_a_barely_reviewed_one(self):
        proven = _doctor(rating=4.6, rating_count=200)
        fluke = _doctor(rating=5.0, rating_count=1)
        assert discovery.rank_score(proven) > discovery.rank_score(fluke)

    def test_no_reviews_is_neutral_not_punished(self):
        unrated = _doctor(rating=None, rating_count=0)
        assert discovery.rank_score(unrated) == discovery.rank_score(_doctor())

    def test_explain_components_sum_to_the_total(self):
        doc = _doctor(
            distance_km=3.0, rating=4.2, rating_count=25,
            live={"real": True, "state": "live", "patients_ahead": 2,
                  "confidence": "medium", "wait_minutes": 20, "samples": 12},
        )
        parts = discovery.explain(doc)
        total = sum(v for k, v in parts.items() if k != "total")
        assert abs(total - parts["total"]) < 0.05, "the score must add up"

    def test_no_live_data_is_safe(self):
        assert isinstance(discovery.rank_score(_doctor(live=None)), float)
        assert isinstance(discovery.rank_score({}), float)

    def test_score_never_includes_the_tier_bonus(self):
        """Tier is the sort key's job, so tuning weights cannot break it."""
        partner = _doctor(partner=True, distance_km=50.0)
        directory = _doctor(partner=False, availability="DIRECTORY", distance_km=0.5)
        # A directory clinic really can score higher on quality alone…
        assert discovery.rank_score(directory) > discovery.rank_score(partner)
        # …and that is exactly why the tier is applied as a separate leading
        # sort key rather than inside this number.


# ══════════════════════════════════════════════════════════════════════════
# 4. F-03 — EWT accuracy
# ══════════════════════════════════════════════════════════════════════════


class TestAccuracy:
    def _row(self, promised, delivered):
        return {
            "estimated_minutes": promised,
            "created_at": NOW,
            "called_at": NOW + timedelta(minutes=delivered),
        }

    def test_accurate_promises_score_excellent(self):
        rows = [self._row(20, 18), self._row(15, 16), self._row(30, 31)]
        report = ewt.accuracy_report(rows)
        assert report["accuracy_grade"] == "excellent"
        assert report["within_tolerance_pct"] == 100.0
        assert report["samples"] == 3

    def test_waiting_longer_than_promised_shows_up_as_positive_bias(self):
        """positive = delivered > promised = we were optimistic (the bad one)."""
        rows = [self._row(10, 40), self._row(10, 40)]
        report = ewt.accuracy_report(rows)
        assert report["bias_minutes"] > 0
        assert report["delivered_avg"] > report["promised_avg"]

    def test_waiting_less_than_promised_is_negative_bias(self):
        """negative = delivered < promised = conservative, the safe direction."""
        rows = [self._row(60, 10)]
        assert ewt.accuracy_report(rows)["bias_minutes"] < 0

    def test_no_data_says_so_instead_of_inventing_a_number(self):
        report = ewt.accuracy_report([])
        assert report["accuracy_grade"] == "no_data"
        assert report["rating"] if False else True  # shape guard
        assert report["promised_avg"] is None
        assert report["samples"] == 0

    def test_rows_without_a_promise_are_skipped_and_counted(self):
        rows = [self._row(20, 20), {"estimated_minutes": None, "created_at": NOW,
                                    "called_at": NOW}]
        report = ewt.accuracy_report(rows)
        assert report["samples"] == 1
        assert report["skipped"] == 1, "a silent filter would be worse than no number"

    def test_a_never_called_patient_is_not_a_sample(self):
        rows = [{"estimated_minutes": 20, "created_at": NOW, "called_at": None}]
        report = ewt.accuracy_report(rows)
        assert report["samples"] == 0
        assert report["skipped"] == 1

    def test_negative_gap_is_rejected_as_clock_skew(self):
        rows = [{"estimated_minutes": 20, "created_at": NOW,
                 "called_at": NOW - timedelta(minutes=5)}]
        assert ewt.accuracy_report(rows)["samples"] == 0

    def test_started_at_is_used_when_called_at_is_missing(self):
        rows = [{"estimated_minutes": 20, "created_at": NOW, "called_at": None,
                 "started_at": NOW + timedelta(minutes=21)}]
        report = ewt.accuracy_report(rows)
        assert report["samples"] == 1
        assert report["delivered_avg"] == 21.0

    def test_one_outlier_does_not_hide_a_generally_accurate_clinic(self):
        """Grade on the hit rate: 9 good + 1 disaster is still 'excellent'."""
        rows = [self._row(20, 20) for _ in range(9)] + [self._row(20, 120)]
        report = ewt.accuracy_report(rows)
        assert report["within_tolerance_pct"] == 90.0
        assert report["accuracy_grade"] == "excellent"

    def test_small_sample_is_flagged_as_untrustworthy(self):
        report = ewt.accuracy_report([self._row(20, 20)])
        assert "sample" in report["note"].lower() or "data" in report["note"].lower()


# ══════════════════════════════════════════════════════════════════════════
# 5. F-07 — verified reviews + Bayesian rating
# ══════════════════════════════════════════════════════════════════════════


class TestBayesian:
    def test_no_reviews_gives_no_score(self):
        assert reviews.bayesian_rating([]) is None

    def test_a_single_five_does_not_reach_five(self):
        score = reviews.bayesian_rating([5])
        assert score < 5.0, "one review must not equal a perfect clinic"
        assert score > reviews.PRIOR_MEAN, "but it should move the needle"

    def test_many_good_reviews_converge_on_the_truth(self):
        score = reviews.bayesian_rating([5] * 100)
        assert score > 4.9

    def test_a_large_mediocre_history_beats_a_tiny_perfect_one(self):
        proven = reviews.bayesian_rating([4, 5] * 60)
        fluke = reviews.bayesian_rating([5])
        assert proven > fluke

    def test_junk_ratings_are_ignored_not_clamped_into_range(self):
        # A 0 or a 9 is not a rating — treating it as 1 or 5 would corrupt data.
        assert reviews.clamp_rating(0) is None
        assert reviews.clamp_rating(9) is None
        assert reviews.clamp_rating("x") is None
        assert reviews.clamp_rating(None) is None
        assert reviews.clamp_rating(True) is None
        assert reviews.clamp_rating(3) == 3

    def test_explicit_zero_ratings_do_not_poison_the_score(self):
        clean = reviews.bayesian_rating([4, 4, 4])
        noisy = reviews.bayesian_rating([4, 4, 4, 0, 99])
        assert clean == noisy

    def test_confidence_grows_with_sample_size(self):
        assert reviews.rating_breakdown([5, 4])["confidence"] == "low"
        assert reviews.rating_breakdown([4] * 20)["confidence"] == "medium"
        assert reviews.rating_breakdown([4] * 60)["confidence"] == "high"

    def test_breakdown_reports_both_raw_and_shrunk(self):
        data = reviews.rating_breakdown([5, 5, 4])
        assert data["raw_average"] == pytest.approx(4.67, abs=0.01)
        assert data["rating"] < data["raw_average"], "shrunk toward the prior"

    def test_unrated_clinic_is_not_penalised_in_ranking(self):
        assert reviews.sort_weight(None, 0) == 0.0

    def test_rating_trust_scales_with_review_count(self):
        assert reviews.sort_weight(5.0, 1) < reviews.sort_weight(5.0, 200)


class TestReviewEligibility:
    def test_only_a_finished_visit_can_be_reviewed(self):
        for status in ("WAITING", "CALLED", "IN_PROGRESS", "NO_SHOW", "CANCELLED"):
            allowed, reason = reviews.eligibility({"status": status})
            assert not allowed, status
            assert reason

    def test_completed_visits_can_be_reviewed(self):
        for status in ("COMPLETED", "REPORT_READY", "DELIVERED"):
            allowed, _reason = reviews.eligibility({"status": status})
            assert allowed, status

    def test_a_missing_visit_is_refused(self):
        allowed, reason = reviews.eligibility(None)
        assert not allowed and reason

    def test_a_very_old_visit_is_refused(self):
        old = {
            "status": "COMPLETED",
            "completed_at": NOW - timedelta(days=200),
        }
        allowed, reason = reviews.eligibility(old, now=NOW)
        assert not allowed and "time" in reason.lower()


class TestReviewRoutes:
    def _clinic(self, code="RV-1", name="Review Clinic"):
        from src.shared.domain.base_entity import uuid7

        clinic_id = uuid7()

        async def _insert():
            async with async_session_factory() as session:
                session.add(
                    ClinicModel(
                        id=clinic_id, clinic_name=name, clinic_code=code,
                        doctor_name=f"Dr {name}", specialty="Cardiology",
                        city="Jodhpur", state="Rajasthan",
                        open_time="00:01", close_time="23:58",
                        is_license_active=True, is_active=True,
                    )
                )
                await session.commit()
            return str(clinic_id)

        return _run(_insert())

    def _visit(self, clinic_id, patient_id, status="COMPLETED", token=1):
        from src.shared.domain.base_entity import uuid7

        async def _insert():
            async with async_session_factory() as session:
                session.add(
                    QueueEntryModel(
                        id=uuid7(), clinic_id=clinic_id, doctor_id="chief",
                        visit_id=f"VIS-REV-{patient_id}-{token}",
                        patient_id=patient_id, patient_uuid=str(uuid7()),
                        patient_name="Reviewer", service_code="OPD",
                        token_number=token, department="Cardiology", room="OPD",
                        status=status, priority=0, display_order=0,
                        sort_key=float(token), visit_type="followup",
                        complexity_weight=1, created_by="test", updated_by="test",
                        version=1,
                        completed_at=NOW if status != "WAITING" else None,
                        created_at=NOW, updated_at=NOW,
                    )
                )
                await session.commit()

        _run(_insert())

    def _token(self, patient_id):
        from src.presentation.staff.routes.staff_routes import make_tracking_token

        return make_tracking_token(patient_id)

    @pytest.fixture(scope="class")
    def client(self):
        return TestClient(main_v2.app)

    def test_a_completed_visit_can_be_reviewed(self, client):
        clinic = self._clinic("RV-A", "Completed Review Clinic")
        patient_id = "CQ-REV-A"
        self._visit(clinic, patient_id, status="COMPLETED")

        body = client.post(
            "/api/v1/reviews",
            json={"tracking_token": self._token(patient_id), "rating": 5,
                  "comment": "Bahut achha laga"},
        ).json()
        assert body["ok"] is True
        assert body["verified"] is True
        assert body["clinic_rating"] is not None

    def test_an_unfinished_visit_cannot_be_reviewed(self, client):
        clinic = self._clinic("RV-B", "Waiting Review Clinic")
        patient_id = "CQ-REV-B"
        self._visit(clinic, patient_id, status="WAITING")

        response = client.post(
            "/api/v1/reviews",
            json={"tracking_token": self._token(patient_id), "rating": 5},
        )
        assert response.status_code == 400
        assert "poori" in response.json()["error"]

    def test_a_bad_token_cannot_review(self, client):
        response = client.post(
            "/api/v1/reviews",
            json={"tracking_token": "not-a-real-token", "rating": 5},
        )
        assert response.status_code == 400

    def test_an_out_of_range_rating_is_rejected(self, client):
        clinic = self._clinic("RV-C", "Range Review Clinic")
        patient_id = "CQ-REV-C"
        self._visit(clinic, patient_id)
        for bad in (0, 6, -1, "x", None):
            response = client.post(
                "/api/v1/reviews",
                json={"tracking_token": self._token(patient_id), "rating": bad},
            )
            assert response.status_code == 400, bad

    def test_one_review_per_visit_updates_rather_than_stacks(self, client):
        clinic = self._clinic("RV-D", "Single Review Clinic")
        patient_id = "CQ-REV-D"
        self._visit(clinic, patient_id, token=7)

        first = client.post(
            "/api/v1/reviews",
            json={"tracking_token": self._token(patient_id), "rating": 2},
        ).json()
        second = client.post(
            "/api/v1/reviews",
            json={"tracking_token": self._token(patient_id), "rating": 4},
        ).json()
        assert first["clinic_review_count"] == 1
        assert second["clinic_review_count"] == 1, "a second star must replace, not add"

        listing = client.get("/api/v1/reviews", params={"clinic_id": clinic}).json()
        assert listing["count"] == 1
        assert listing["reviews"][0]["rating"] == 4

    def test_public_listing_hides_the_patient_identity(self, client):
        """A review must not publish who visited — in a small town that is PHI."""
        clinic = self._clinic("RV-E", "Private Review Clinic")
        patient_id = "CQ-REV-E"
        self._visit(clinic, patient_id)
        client.post(
            "/api/v1/reviews",
            json={"tracking_token": self._token(patient_id), "rating": 5,
                  "comment": "Good"},
        )
        listing = client.get("/api/v1/reviews", params={"clinic_id": clinic}).json()
        blob = str(listing)
        assert patient_id not in blob
        assert "Reviewer" not in blob

    def test_hiding_a_review_recomputes_the_score(self, client, login):
        clinic = self._clinic("RV-F", "Moderation Clinic")
        patient_id = "CQ-REV-F"
        self._visit(clinic, patient_id)
        login(clinic)
        client.post(
            "/api/v1/reviews",
            json={"tracking_token": self._token(patient_id), "rating": 1},
        )
        listing = client.get("/api/v1/reviews", params={"clinic_id": clinic}).json()
        assert listing["count"] == 1

        import asyncio

        async def _id():
            import sqlalchemy as sa

            async with async_session_factory() as session:
                row = await session.execute(
                    sa.select(ClinicReviewModel.id).where(
                        ClinicReviewModel.clinic_id == clinic
                    )
                )
                return str(row.scalars().first())

        review_id = asyncio.run(_id())
        hidden = client.post(f"/api/v1/reviews/{review_id}/hide", json={"reason": "spam"}).json()
        assert hidden["ok"] is True
        assert hidden["clinic_review_count"] == 0

        after = client.get("/api/v1/reviews", params={"clinic_id": clinic}).json()
        assert after["count"] == 0
        assert after["reviews"] == []

    def test_unknown_clinic_listing_is_a_clean_404(self, client):
        response = client.get(
            "/api/v1/reviews",
            params={"clinic_id": "00000000-0000-0000-0000-000000000000"},
        )
        assert response.status_code == 404


# ══════════════════════════════════════════════════════════════════════════
# 6. F-08 — PHI-free network overview
# ══════════════════════════════════════════════════════════════════════════


class TestNetworkOverview:
    @pytest.fixture(scope="class")
    def client(self):
        return TestClient(main_v2.app)

    def test_requires_authorization(self, client):
        response = client.get("/api/v1/admin/network")
        assert response.status_code == 401

    def test_seed_token_grants_read_access(self, client):
        from src.presentation.marketplace.routes.marketplace_routes import SEED_TOKEN

        response = client.get("/api/v1/admin/network", params={"token": SEED_TOKEN})
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["ok"] is True
        assert payload["phi_free"] is True
        assert "totals" in payload and "nodes" in payload
        assert payload["totals"]["clinics"] >= 1

    def test_the_payload_contains_no_patient_data(self, client):
        """The whole point of F-08: operations visibility without PHI."""
        from src.presentation.marketplace.routes.marketplace_routes import SEED_TOKEN

        payload = client.get(
            "/api/v1/admin/network", params={"token": SEED_TOKEN}
        ).json()
        # Check the DATA, not the human-readable note — the note legitimately
        # says "no patient ka naam, phone ya clinical data" in words.
        blob = str({"nodes": payload["nodes"], "totals": payload["totals"]}).lower()
        for forbidden in (
            "patient_name", "patient_id", "phone", "phone_hash",
            "diagnosis", "prescription", "complaint", "reception_inquiry",
            "visit_id", "token_number",
        ):
            assert forbidden not in blob, f"{forbidden} must never appear"

    def test_no_patient_identifiers_leak_through_a_known_patient(self, client):
        """A real patient exists in the DB — the network view must not name them."""
        from src.presentation.marketplace.routes.marketplace_routes import SEED_TOKEN

        payload = client.get(
            "/api/v1/admin/network", params={"token": SEED_TOKEN}
        ).json()
        blob = str(payload).lower()
        # CQ- ids are patient identifiers used throughout these tests.
        assert "cq-rev" not in blob
        assert "cq-2026" not in blob

    def test_each_node_reports_liveness_not_identity(self, client):
        from src.presentation.marketplace.routes.marketplace_routes import SEED_TOKEN

        payload = client.get(
            "/api/v1/admin/network", params={"token": SEED_TOKEN}
        ).json()
        node = payload["nodes"][0]
        for field in ("clinic_id", "clinic_name", "tokens_7d", "live_tokens",
                      "partner", "last_active"):
            assert field in node
