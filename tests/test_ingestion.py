"""Module 6 ingestion tests (master blueprint BLOCK 5 · M6-01 … M6-05).

Run:  python -m pytest tests/test_ingestion.py -q

The worker runs on GitHub Actions, so what is testable here is the contract it
must obey — which is also where the harm would be:

  1. **Profile validation** — a wrong phone number on a public listing sends a
     patient to a stranger, so a phone that is not a plausible 10-digit mobile
     is dropped, not stored hopefully.
  2. **The extractor-shape tolerance** — LLM extraction returns a bare list, a
     wrapper, an object, or a JSON string of any of those. Unwrapping them is
     fine; inventing a profile is not.
  3. **Opt-out is permanent and enforced before any write** — an opt-out that
     only affects one batch is not an opt-out.
  4. **A crawled listing is labelled public and unclaimed**, and the directory
     offers the clinic a way to claim it or remove it.
  5. **The worker's own validation agrees with the server's**, because a worker
     that drops nothing and a server that drops everything is a silent failure.

The worker module is imported directly (`workers/crawl_doctors/main.py`) — its
crawl4ai/playwright imports are inside functions precisely so this works without
a 400 MB browser.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_TEST_DB = ROOT / "test_ingestion.db"
if _TEST_DB.exists():
    try:
        _TEST_DB.unlink()
    except Exception:
        pass

os.environ["GHOS_DB_URL"] = f"sqlite:///{_TEST_DB}"
os.environ["SYSTEM_AI_FALLBACK_ENABLED"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import main_v2  # noqa: E402
from src.infrastructure.clinic.models.clinic_model import ClinicModel  # noqa: E402
from src.infrastructure.clinic.models.crawl_model import (  # noqa: E402
    DoctorCrawlRunModel,
    ProfileValidationError,
    coerce_profiles,
    doctor_profile_schema,
    normalise_profile,
    profile_identity,
)
from src.shared.infrastructure.database import async_session_factory  # noqa: E402

main_v2.Base.metadata.create_all(bind=main_v2.engine)
main_v2._migrate_sqlite_columns()

# Stamped in the past so these rows are never the "most recent queue entry"
# that other test modules rely on.
NOW = datetime.now(timezone.utc) - timedelta(hours=2)

TOKEN = "GIL-DEMO-SEED-2026"


def _run(coro):
    import asyncio

    return asyncio.run(coro)


def _load_worker():
    """Import the worker module without needing crawl4ai installed.

    The module is registered in ``sys.modules`` BEFORE ``exec_module`` because
    ``@dataclass`` resolves its field types through
    ``sys.modules[cls.__module__]`` — without it, the decorator raises
    ``AttributeError: 'NoneType' object has no attribute '__dict__'``.
    """
    name = "crawl_worker_under_test"
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "workers" / "crawl_doctors" / "main.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


worker = _load_worker()


@pytest.fixture(scope="module")
def client():
    return TestClient(main_v2.app)


# ══════════════════════════════════════════════════════════════════════════
# 1. Profile validation
# ══════════════════════════════════════════════════════════════════════════


class TestProfileValidation:
    def test_a_clean_profile_passes(self):
        profile = normalise_profile(
            {
                "doctor_name": "Anita Sharma",
                "clinic_name": "Sharma Family Clinic",
                "specialty": "General Physician",
                "city": "Jodhpur",
                "phone": "9829012345",
            }
        )
        assert profile["doctor_name"] == "Anita Sharma"
        assert profile["phone"] == "9829012345"

    def test_a_name_is_required(self):
        with pytest.raises(ProfileValidationError):
            normalise_profile({"clinic_name": "Some Clinic"})

    def test_a_name_with_no_letters_is_a_parsing_artefact(self):
        for junk in ("-", "123", "..."):
            with pytest.raises(ProfileValidationError):
                normalise_profile({"doctor_name": junk})

    def test_placeholder_names_are_not_names(self):
        """A listing called "N/A (N/A Clinic)" is worse than no listing."""
        for junk in ("N/A", "n/a", "N.A.", "None", "null", "Unknown",
                     "Not available", "TBD", "test", "xxx", "Doctor", "Dr"):
            with pytest.raises(ProfileValidationError, match="placeholder"):
                normalise_profile({"doctor_name": junk})

    def test_a_real_name_that_merely_contains_a_placeholder_word_survives(self):
        """The guard must not eat a genuine name just because it looks odd."""
        for good in ("Dr. Naresh Kumar", "Null Chand", "Testa Devi", "Naaz Sheikh"):
            profile = normalise_profile({"doctor_name": good})
            assert profile["doctor_name"]

    def test_an_untrustworthy_phone_is_dropped_not_stored(self):
        """A wrong number sends a patient to a stranger."""
        for bad in ("12345", "0000000000", "1234567890", "+1 555 0100", "abc"):
            profile = normalise_profile({"doctor_name": "Real Doctor", "phone": bad})
            assert "phone" not in profile, bad

    def test_valid_phone_formats_are_normalised(self):
        for raw, expected in (
            ("9829012345", "9829012345"),
            ("+91 98290 12345", "9829012345"),
            ("919829012345", "9829012345"),
            ("09829012345", "9829012345"),
            ("98290-12345", "9829012345"),
        ):
            profile = normalise_profile({"doctor_name": "Phone Doctor", "phone": raw})
            assert profile.get("phone") == expected, raw

    def test_unknown_keys_are_dropped(self):
        """An extractor emitting a new field must not write it unreviewed."""
        profile = normalise_profile(
            {"doctor_name": "Extra Doctor", "invented_field": "x", "sql": "DROP TABLE"}
        )
        assert "invented_field" not in profile
        assert "sql" not in profile

    def test_over_long_values_are_truncated_not_rejected(self):
        """One verbose address must not discard an otherwise good profile."""
        profile = normalise_profile(
            {"doctor_name": "Verbose Doctor", "address": "x" * 5000}
        )
        assert len(profile["address"]) == 1000

    def test_zero_zero_coordinates_are_a_placeholder_not_a_place(self):
        profile = normalise_profile(
            {"doctor_name": "Geo Doctor", "latitude": 0.0, "longitude": 0.0}
        )
        assert "latitude" not in profile
        assert "longitude" not in profile

    def test_out_of_range_coordinates_are_dropped(self):
        profile = normalise_profile(
            {"doctor_name": "Geo Doctor", "latitude": 999, "longitude": -999}
        )
        assert "latitude" not in profile
        assert "longitude" not in profile

    def test_real_coordinates_are_kept(self):
        profile = normalise_profile(
            {"doctor_name": "Geo Doctor", "latitude": 26.2389, "longitude": 73.0243}
        )
        assert profile["latitude"] == 26.2389

    def test_identity_is_stable_across_sources(self):
        """The same doctor listed on two pages must not become twins."""
        a = profile_identity({"doctor_name": "Anita Sharma", "city": "Jodhpur", "clinic_name": "SFC"})
        b = profile_identity({"doctor_name": "anita sharma", "city": "JODHPUR", "clinic_name": "sfc"})
        assert a == b


class TestExtractorShapeTolerance:
    def test_a_bare_list(self):
        assert len(coerce_profiles([{"doctor_name": "A"}])) == 1

    def test_a_doctors_wrapper(self):
        assert len(coerce_profiles({"doctors": [{"doctor_name": "A"}]})) == 1

    def test_other_common_wrappers(self):
        for key in ("profiles", "data", "results", "items", "records"):
            assert len(coerce_profiles({key: [{"doctor_name": "A"}]})) == 1, key

    def test_a_single_object(self):
        assert len(coerce_profiles({"doctor_name": "Solo"})) == 1

    def test_a_json_string_is_parsed(self):
        raw = json.dumps({"doctors": [{"doctor_name": "A"}, {"doctor_name": "B"}]})
        assert len(coerce_profiles(raw)) == 2

    def test_a_broken_json_string_yields_nothing_not_a_crash(self):
        assert coerce_profiles("{not json") == []

    def test_junk_yields_nothing(self):
        for junk in (None, "", 42, object(), {}):
            assert coerce_profiles(junk) == []

    def test_non_dict_items_are_skipped(self):
        assert len(coerce_profiles([{"doctor_name": "A"}, "junk", 5])) == 1


class TestSchemaServedToWorker:
    def test_the_schema_lists_the_required_field(self):
        schema = doctor_profile_schema()
        assert "doctor_name" in schema["required"]
        assert schema["type"] == "object"

    def test_the_schema_declares_limits(self):
        schema = doctor_profile_schema()
        assert schema["properties"]["address"]["maxLength"] == 1000

    def test_the_endpoint_serves_it_and_fails_closed(self, client):
        assert client.get("/api/v1/ingest/schema").status_code == 401
        body = client.get("/api/v1/ingest/schema", params={"token": TOKEN}).json()
        assert body["ok"] is True
        assert "doctor_name" in body["schema"]["required"]
        assert body["max_profiles_per_batch"] >= 1


# ══════════════════════════════════════════════════════════════════════════
# 2. The worker agrees with the server
# ══════════════════════════════════════════════════════════════════════════


class TestWorkerAgreesWithServer:
    def test_the_worker_drops_the_same_bad_profiles(self):
        bad = {"doctor_name": "-", "phone": "123"}
        assert worker.validate_profile(bad) is None
        with pytest.raises(ProfileValidationError):
            normalise_profile(bad)

    def test_the_worker_keeps_the_same_good_profile(self):
        good = {"doctor_name": "Anita Sharma", "city": "Jodhpur", "phone": "9829012345"}
        assert worker.validate_profile(good)["doctor_name"] == "Anita Sharma"
        assert normalise_profile(good)["doctor_name"] == "Anita Sharma"

    def test_the_worker_normalises_phone_the_same_way(self):
        raw = {"doctor_name": "Phone Doctor", "phone": "+91 98290 12345"}
        assert worker.validate_profile(raw)["phone"] == normalise_profile(raw)["phone"]

    def test_the_worker_strips_a_leading_dr(self):
        assert worker.validate_profile({"doctor_name": "Dr. Anita Sharma"})["doctor_name"] == "Anita Sharma"

    def test_the_worker_dedupes_within_a_batch(self):
        profiles = [
            {"doctor_name": "A", "city": "X", "clinic_name": "C"},
            {"doctor_name": "a", "city": "x", "clinic_name": "c"},
            {"doctor_name": "B", "city": "X", "clinic_name": "C"},
        ]
        assert len(worker.dedupe(profiles)) == 2

    def test_the_worker_coerces_the_same_shapes(self):
        for payload in (
            [{"doctor_name": "A"}],
            {"doctors": [{"doctor_name": "A"}]},
            {"doctor_name": "A"},
            json.dumps([{"doctor_name": "A"}]),
        ):
            assert len(worker._coerce(payload)) == 1, payload

    def test_city_and_state_are_filled_only_when_the_page_is_silent(self):
        """Never overwrite extracted text with config."""
        target = worker.Target(url="https://x", city="Jodhpur", state="Rajasthan")
        filled = worker.stamp_target({"doctor_name": "A"}, target)
        assert filled["city"] == "Jodhpur"
        assert filled["source_url"] == "https://x"

        kept = worker.stamp_target({"doctor_name": "A", "city": "Ajmer"}, target)
        assert kept["city"] == "Ajmer", "the page is the authority on what the page says"

    def test_the_worker_ignores_zero_zero_coordinates_coercion(self):
        """The worker sends them; the server drops them. Prove the server does."""
        profile = normalise_profile(
            {"doctor_name": "Geo Doctor", "latitude": 0.0, "longitude": 0.0}
        )
        assert "latitude" not in profile


# ══════════════════════════════════════════════════════════════════════════
# 3. Ingest endpoint
# ══════════════════════════════════════════════════════════════════════════


def _ingest(client, profiles, **over):
    body = {"run_label": "test-run", "triggered_by": "pytest", "profiles": profiles}
    body.update(over)
    return client.post("/api/v1/ingest/doctors", params={"token": TOKEN}, json=body)


class TestIngestEndpoint:
    def test_it_fails_closed_without_the_token(self, client):
        assert client.post("/api/v1/ingest/doctors", json={"profiles": []}).status_code == 401
        assert client.post(
            "/api/v1/ingest/doctors", params={"token": "wrong"}, json={"profiles": []}
        ).status_code == 401

    def test_a_batch_creates_unclaimed_public_listings(self, client):
        response = _ingest(client, [
            {"doctor_name": "Crawled One", "clinic_name": "Crawled Clinic",
             "city": "Udaipur", "specialty": "Cardiology", "phone": "9829011111"},
            {"doctor_name": "Crawled Two", "clinic_name": "Crawled Clinic",
             "city": "Udaipur", "specialty": "Cardiology"},
        ])
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["ok"] is True
        assert body["created"] == 2
        assert body["run_id"]

        async def _rows():
            import sqlalchemy as sa

            async with async_session_factory() as session:
                row = await session.execute(
                    sa.select(ClinicModel).where(ClinicModel.doctor_name == "Crawled One")
                )
                return row.scalars().first()

        clinic = _run(_rows())
        assert clinic is not None
        assert clinic.source == "crawl"
        assert clinic.claim_status == "unclaimed"
        # A crawled clinic must NOT look like a partner — no live queue exists.
        assert clinic.is_license_active is False

    def test_an_empty_batch_is_refused_with_a_clear_message(self, client):
        response = client.post(
            "/api/v1/ingest/doctors", params={"token": TOKEN}, json={"profiles": []}
        )
        assert response.status_code == 400
        assert "profiles" in response.json()["error"]

    def test_an_oversized_batch_is_refused(self, client):
        profiles = [{"doctor_name": f"Bulk {i}"} for i in range(250)]
        response = _ingest(client, profiles)
        assert response.status_code == 413
        assert response.json()["received"] == 250

    def test_a_bare_list_body_works(self, client):
        response = client.post(
            "/api/v1/ingest/doctors",
            params={"token": TOKEN},
            json=[{"doctor_name": "Bare List Doctor", "city": "Kota"}],
        )
        assert response.status_code == 200
        assert response.json()["created"] == 1

    def test_invalid_profiles_are_skipped_and_counted_by_reason(self, client):
        response = _ingest(client, [
            {"doctor_name": "Valid Doctor", "city": "Alwar"},
            {"doctor_name": "--"},
            {"clinic_name": "No Name Clinic"},
        ])
        body = response.json()
        assert body["created"] == 1
        assert body["skipped"] == 2
        assert body["skipped_reasons"], "a worker that cannot see WHY cannot fix itself"

    def test_skip_reasons_are_stable_codes_not_junk_values(self, client):
        """Bucketing by message text gave one counter per distinct junk value
        ("'N/A'": 1, "'--'": 1), which tells a worker nothing about the SHAPE of
        its own failures."""
        body = _ingest(client, [
            {"doctor_name": "N/A"},
            {"doctor_name": "--"},
            {"doctor_name": "Unknown"},
            {"clinic_name": "Nameless"},
            # A second "N/A" must land in the SAME bucket as the first.
            {"doctor_name": "n/a"},
        ]).json()
        reasons = body["skipped_reasons"]
        assert body["skipped"] == 5
        # "N/A", "Unknown" and "n/a" are all the same failure → one bucket.
        assert reasons.get("placeholder_name") == 3, reasons
        # "--" has no letters at all, so it is caught as a parsing artefact
        # before the placeholder check — a different, equally correct bucket.
        assert reasons.get("nameless") == 1, reasons
        assert reasons.get("missing_name") == 1, reasons
        # And no bucket is named after a junk value.
        for key in reasons:
            assert "N/A" not in key and "--" not in key, reasons

    def test_a_batch_of_only_junk_is_accepted_with_a_full_report(self, client):
        """A 400 would say "bad request". The truth is "we received it and
        rejected every profile, here is why" — which is more useful."""
        response = _ingest(client, [{"doctor_name": "N/A"}, {"doctor_name": "TBD"}])
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["received"] == 2
        assert body["created"] == 0
        assert body["skipped"] == 2
        assert body["skipped_reasons"].get("placeholder_name") == 2

    def test_the_run_row_records_the_bucketed_reasons(self, client):
        _ingest(
            client,
            [{"doctor_name": "N/A"}, {"doctor_name": "Run Bucket Doctor", "city": "Nagaur"}],
            run_label="bucket-run",
        )

        async def _run_row():
            import sqlalchemy as sa

            async with async_session_factory() as session:
                row = await session.execute(
                    sa.select(DoctorCrawlRunModel)
                    .where(DoctorCrawlRunModel.run_label == "bucket-run")
                    .limit(1)
                )
                return row.scalars().first()

        run = _run(_run_row())
        assert "placeholder_name=1" in run.skipped_reasons
        assert run.profiles_created == 1

    def test_re_ingesting_updates_rather_than_duplicating(self, client):
        first = _ingest(client, [{"doctor_name": "Repeat Doctor", "city": "Bhilwara"}]).json()
        assert first["created"] == 1
        second = _ingest(client, [{"doctor_name": "Repeat Doctor", "city": "Bhilwara"}]).json()
        assert second["created"] == 0
        assert second["updated"] == 1

    def test_a_run_row_records_the_outcome(self, client):
        _ingest(
            client,
            [{"doctor_name": "Run Row Doctor", "city": "Pali"}],
            run_label="pali-run",
            urls_attempted=4,
        )

        async def _run_row():
            import sqlalchemy as sa

            async with async_session_factory() as session:
                row = await session.execute(
                    sa.select(DoctorCrawlRunModel)
                    .where(DoctorCrawlRunModel.run_label == "pali-run")
                    .limit(1)
                )
                return row.scalars().first()

        run = _run(_run_row())
        assert run is not None
        assert run.status == "COMPLETED"
        assert run.profiles_found == 1
        assert run.urls_attempted == 4
        assert run.finished_at is not None

    def test_the_run_history_is_token_gated(self, client):
        assert client.get("/api/v1/ingest/runs").status_code == 401
        body = client.get("/api/v1/ingest/runs", params={"token": TOKEN}).json()
        assert body["ok"] is True
        assert isinstance(body["runs"], list)


# ══════════════════════════════════════════════════════════════════════════
# 4. Opt-out — the rule that must hold before any write
# ══════════════════════════════════════════════════════════════════════════


class TestOptOut:
    def _crawled_clinic(self, client, name: str, city: str) -> str:
        _ingest(client, [{"doctor_name": name, "city": city, "clinic_name": f"{name} Clinic"}])

        async def _id():
            import sqlalchemy as sa

            async with async_session_factory() as session:
                row = await session.execute(
                    sa.select(ClinicModel.id).where(ClinicModel.doctor_name == name)
                )
                return str(row.scalars().first())

        return _run(_id())

    def test_opting_out_removes_the_listing(self, client):
        clinic_id = self._crawled_clinic(client, "Opt Out Doctor", "Sikar")
        body = client.post(
            "/api/v1/marketplace/opt-out",
            json={"clinic_id": clinic_id, "reason": "does not want to be listed"},
        ).json()
        assert body["ok"] is True

        # The public directory must not show it any more.
        listing = client.get("/api/v1/marketplace/doctors").json()
        assert clinic_id not in [d["id"] for d in listing["doctors"]]

    def test_opting_out_records_the_reason(self, client):
        clinic_id = self._crawled_clinic(client, "Reason Doctor", "Tonk")
        client.post(
            "/api/v1/marketplace/opt-out",
            json={"clinic_id": clinic_id, "reason": "wrong phone number"},
        )

        async def _row():
            import sqlalchemy as sa
            import uuid as _uuid

            async with async_session_factory() as session:
                return await session.get(ClinicModel, _uuid.UUID(clinic_id))

        clinic = _run(_row())
        assert clinic.claim_status == "opted_out"
        assert clinic.opted_out_at is not None
        assert "phone" in clinic.opt_out_reason

    def test_a_later_crawl_run_cannot_resurrect_an_opt_out(self, client):
        """An opt-out that only affects one batch is not an opt-out."""
        self._crawled_clinic(client, "Never Again Doctor", "Baran")

        async def _id():
            import sqlalchemy as sa

            async with async_session_factory() as session:
                row = await session.execute(
                    sa.select(ClinicModel.id).where(
                        ClinicModel.doctor_name == "Never Again Doctor"
                    )
                )
                return str(row.scalars().first())

        clinic_id = _run(_id())
        client.post("/api/v1/marketplace/opt-out", json={"clinic_id": clinic_id})

        # The crawler finds them again on a fresh page and posts them again.
        body = _ingest(client, [
            {"doctor_name": "Never Again Doctor", "city": "Baran",
             "clinic_name": "Never Again Doctor Clinic"}
        ]).json()
        assert body["created"] == 0
        assert body["updated"] == 0
        assert body["skipped"] == 1
        assert body["skipped_reasons"].get("opted_out") == 1

    def test_the_opt_out_register_is_token_gated_and_lists_reasons(self, client):
        assert client.get("/api/v1/marketplace/opt-out").status_code == 401
        body = client.get(
            "/api/v1/marketplace/opt-out", params={"token": TOKEN}
        ).json()
        assert body["ok"] is True
        assert body["total"] >= 1
        assert all("reason" in row for row in body["opted_out"])

    def test_opt_out_needs_a_clinic_id(self, client):
        assert client.post("/api/v1/marketplace/opt-out", json={}).status_code == 400

    def test_an_opted_out_clinic_cannot_re_claim(self, client):
        clinic_id = self._crawled_clinic(client, "Claim Guard Doctor", "Jhalawar")
        client.post("/api/v1/marketplace/opt-out", json={"clinic_id": clinic_id})
        response = client.post(
            "/api/v1/marketplace/claim", json={"clinic_id": clinic_id}
        )
        assert response.status_code == 400
        assert "opt-out" in response.json()["error"]


# ══════════════════════════════════════════════════════════════════════════
# 5. Claim + the public listing label
# ══════════════════════════════════════════════════════════════════════════


class TestClaim:
    def _crawled_clinic(self, client, name: str, city: str) -> str:
        _ingest(client, [{"doctor_name": name, "city": city, "clinic_name": f"{name} Clinic"}])

        async def _id():
            import sqlalchemy as sa

            async with async_session_factory() as session:
                row = await session.execute(
                    sa.select(ClinicModel.id).where(ClinicModel.doctor_name == name)
                )
                return str(row.scalars().first())

        return _run(_id())

    def test_a_crawled_listing_is_labelled_public_unclaimed(self, client):
        clinic_id = self._crawled_clinic(client, "Label Doctor", "Dausa")
        listing = client.get("/api/v1/marketplace/doctors").json()
        row = next(d for d in listing["doctors"] if d["id"] == clinic_id)
        assert row["is_crawled"] is True
        assert row["claim_status"] == "unclaimed"
        assert row["source"] == "crawl"
        # It must show the "call to confirm" badge, not an open-now promise.
        assert row["availability"] == "DIRECTORY"

    def test_claiming_marks_it_clinic_confirmed(self, client):
        clinic_id = self._crawled_clinic(client, "Claim Doctor", "Churu")
        body = client.post(
            "/api/v1/marketplace/claim", json={"clinic_id": clinic_id}
        ).json()
        assert body["ok"] is True

        listing = client.get("/api/v1/marketplace/doctors").json()
        row = next(d for d in listing["doctors"] if d["id"] == clinic_id)
        assert row["claim_status"] == "claimed"
        # Claiming is NOT onboarding — the live queue still needs a licence.
        assert row["partner"] is False

    def test_claiming_twice_is_idempotent(self, client):
        clinic_id = self._crawled_clinic(client, "Twice Claim Doctor", "Bundi")
        client.post("/api/v1/marketplace/claim", json={"clinic_id": clinic_id})
        again = client.post(
            "/api/v1/marketplace/claim", json={"clinic_id": clinic_id}
        ).json()
        assert again["ok"] is True
        assert again.get("already_claimed") is True

    def test_an_admin_onboarded_clinic_is_not_a_crawled_listing(self, client):
        """The directory must never blur admin/patient/crawler provenance."""
        from src.shared.domain.base_entity import uuid7

        clinic_id = uuid7()

        async def _insert():
            async with async_session_factory() as session:
                session.add(
                    ClinicModel(
                        id=clinic_id, clinic_name="Manually Onboarded",
                        clinic_code="MAN-001", doctor_name="Manual Doctor",
                        specialty="Cardiology", city="Jodhpur", state="Rajasthan",
                        open_time="00:01", close_time="23:58",
                        is_license_active=True, is_active=True,
                    )
                )
                await session.commit()

        _run(_insert())
        listing = client.get("/api/v1/marketplace/doctors").json()
        row = next(d for d in listing["doctors"] if d["id"] == str(clinic_id))
        assert row["is_crawled"] is False
        assert row["source"] == "manual"

    def test_claim_needs_a_clinic_id(self, client):
        assert client.post("/api/v1/marketplace/claim", json={}).status_code == 400

    def test_claiming_an_unknown_clinic_is_a_clean_404(self, client):
        response = client.post(
            "/api/v1/marketplace/claim",
            json={"clinic_id": "00000000-0000-0000-0000-000000000000"},
        )
        assert response.status_code == 404


class TestWorkerPackage:
    """The worker's own files must be coherent — it runs where we cannot debug."""

    def test_the_github_workflow_exists_and_parses(self):
        import yaml

        path = ROOT / ".github" / "workflows" / "ingest-doctors.yml"
        assert path.exists(), "the cron is how the worker runs"
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert "jobs" in workflow
        assert "crawl" in workflow["jobs"]

    def test_the_workflow_is_manual_by_default(self):
        """A cron crawling an example.com placeholder every night is noise."""
        path = ROOT / ".github" / "workflows" / "ingest-doctors.yml"
        text = path.read_text(encoding="utf-8")
        assert "workflow_dispatch" in text
        assert "# schedule:" in text, "the schedule must be opt-in, not live"

    def test_the_workflow_installs_chromium_in_the_worker_not_the_app(self):
        path = ROOT / ".github" / "workflows" / "ingest-doctors.yml"
        text = path.read_text(encoding="utf-8")
        assert "playwright install" in text
        assert "workers/crawl_doctors" in text

    def test_requirements_lists_the_crawler_stack(self):
        text = (ROOT / "workers" / "crawl_doctors" / "requirements.txt").read_text(encoding="utf-8")
        assert "crawl4ai" in text
        assert "playwright" in text

    def test_targets_config_is_valid_json(self):
        data = json.loads(
            (ROOT / "workers" / "crawl_doctors" / "targets.json").read_text(encoding="utf-8")
        )
        assert "targets" in data
        assert isinstance(data["targets"], list)

    def test_the_readme_states_why_the_worker_is_separate(self):
        text = (ROOT / "workers" / "crawl_doctors" / "README.md").read_text(encoding="utf-8")
        assert "100" in text, "the CPU-second budget is the reason, not a preference"
        assert "Chromium" in text

    def test_targets_loader_accepts_both_shapes(self, tmp_path):
        for payload in (
            {"targets": [{"url": "https://a", "city": "X"}]},
            [{"url": "https://a", "city": "X"}],
            ["https://a"],
        ):
            path = tmp_path / "t.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            targets = worker.load_targets(str(path))
            assert len(targets) == 1
            assert targets[0].url == "https://a"

    def test_targets_loader_skips_entries_without_a_url(self, tmp_path):
        path = tmp_path / "t.json"
        path.write_text(json.dumps({"targets": [{"city": "X"}, {"url": "https://b"}]}), encoding="utf-8")
        assert [t.url for t in worker.load_targets(str(path))] == ["https://b"]
