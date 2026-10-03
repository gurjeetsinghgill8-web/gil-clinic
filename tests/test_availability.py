"""Availability, travel and no-show tests (master blueprint BLOCK 2).

Run:  python -m pytest tests/test_availability.py -q

What this file pins, and why each one matters:

  1. **opening_hours** — the directory used to call every licensed clinic
     "OPEN", so a patient could cross a city to a closed shutter. Every branch
     of the rule has a hand-computed test, including the one that matters most:
     *a clinic with no hours configured is never hidden.*
  2. **travel** — the departure alert must not send a patient 25 minutes away
     into a 6-minute wait, and must never invent a distance it was not given.
  3. **E-07 no-show** — a patient who never appears must stop inflating
     everybody else's countdown, and an uncalled patient must never be swept.
  4. **API contract** — the public marketplace must expose availability, honour
     the "🟢 Abhi khula hai" filter, and keep the two-tier partner ranking.

Time is injected everywhere in groups 1–3, so nothing here depends on the
clock. Group 4 deliberately builds clinics whose state is fixed by a closed day
or a holiday (not by the hour) for the same reason.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_TEST_DB = ROOT / "test_availability.db"
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
from src.domain.clinic import opening_hours as oh  # noqa: E402
from src.domain.queue import ewt, travel  # noqa: E402
from src.infrastructure.clinic.models.clinic_model import ClinicModel  # noqa: E402
from src.shared.infrastructure.database import async_session_factory  # noqa: E402

main_v2.Base.metadata.create_all(bind=main_v2.engine)
# The live PythonAnywhere database upgrades itself with this same migrator, so
# running it here also proves the six new `clinics` columns can be added to an
# existing database rather than only to a fresh one.
main_v2._migrate_sqlite_columns()


def weekday_at(target: int, hour: int = 12) -> datetime:
    """A naive (clinic-local) datetime whose weekday() is ``target``.

    Computed rather than hardcoded so the tests cannot silently drift out of
    date, and naive because :func:`oh.local_now` treats naive input as already
    being clinic-local time — which is what a receptionist's wall clock means.
    """
    base = datetime(2026, 10, 1, hour, 0)
    return base + timedelta(days=(target - base.weekday()) % 7)


# ══════════════════════════════════════════════════════════════════════════
# 1. opening_hours — parsing
# ══════════════════════════════════════════════════════════════════════════


class TestParseTime:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("09:00", "09:00"),
            ("9:00", "09:00"),
            ("9", "09:00"),
            ("0900", "09:00"),
            ("09:00:00", "09:00"),
            ("9.30", "09:30"),
            ("9:00 PM", "21:00"),
            ("9:00 am", "09:00"),
            ("12:00 AM", "00:00"),
            ("12:00 PM", "12:00"),
            ("21:45", "21:45"),
        ],
    )
    def test_human_formats_are_understood(self, raw, expected):
        parsed = oh.parse_time(raw)
        assert parsed is not None, raw
        assert parsed.strftime("%H:%M") == expected

    @pytest.mark.parametrize("raw", ["", None, "   ", "abc", "25:00", "10:99", ":"])
    def test_junk_is_rejected_rather_than_guessed(self, raw):
        assert oh.parse_time(raw) is None

    def test_none_means_unknown_not_midnight(self):
        # If this ever returned 00:00 every clinic would look closed all day.
        assert oh.parse_time("") is None


class TestParseClosedDays:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("Sunday", {6}),
            ("sunday", {6}),
            ("sun", {6}),
            ("6", {6}),
            ("sun,sat", {5, 6}),
            ("6,5", {5, 6}),
            ("6 5", {5, 6}),
            ("Sunday,Saturday", {5, 6}),
            ("ravivar,shanivar", {5, 6}),
            ("", set()),
            (None, set()),
            ("notaday", set()),
        ],
    )
    def test_names_numbers_and_hindi_aliases(self, raw, expected):
        assert oh.parse_closed_days(raw) == expected


class TestLocalClock:
    def test_naive_input_is_already_clinic_local(self):
        naive = datetime(2026, 10, 2, 10, 0)
        assert oh.local_now(naive).hour == 10

    def test_utc_is_converted_to_ist(self):
        # 04:30 UTC == 10:00 IST — the conversion the rest of the app relies on.
        from datetime import timezone

        utc = datetime(2026, 10, 2, 4, 30, tzinfo=timezone.utc)
        local = oh.local_now(utc)
        assert (local.hour, local.minute) == (10, 0)


# ══════════════════════════════════════════════════════════════════════════
# 1b. opening_hours — the availability rule
# ══════════════════════════════════════════════════════════════════════════


class TestAvailabilityState:
    HOURS = dict(open_time="09:00", close_time="18:00")

    def test_inside_hours_is_open(self):
        assert oh.availability_state(**self.HOURS, now=weekday_at(0, 11)) == oh.OPEN

    def test_final_hour_warns_instead_of_promising(self):
        # 17:30 with an 18:00 close → 30 min left, inside CLOSING_SOON_MINUTES.
        assert oh.availability_state(**self.HOURS, now=weekday_at(0, 17) + timedelta(minutes=30)) == oh.CLOSING_SOON

    def test_before_opening_is_closed(self):
        assert oh.availability_state(**self.HOURS, now=weekday_at(0, 7)) == oh.CLOSED

    def test_after_closing_is_closed(self):
        assert oh.availability_state(**self.HOURS, now=weekday_at(0, 20)) == oh.CLOSED

    def test_exactly_at_opening_is_open(self):
        assert oh.availability_state(**self.HOURS, now=weekday_at(0, 9)) == oh.OPEN

    def test_exactly_at_closing_is_closed(self):
        assert oh.availability_state(**self.HOURS, now=weekday_at(0, 18)) == oh.CLOSED

    def test_weekly_off_day_is_closed_all_day(self):
        monday = weekday_at(0, 11)
        assert oh.availability_state(
            **self.HOURS, closed_days="Monday", now=monday
        ) == oh.CLOSED

    def test_holiday_beats_a_normal_working_day(self):
        # Tuesday 11:00, within hours, but declared holiday through tomorrow.
        tuesday = weekday_at(1, 11)
        until = (tuesday + timedelta(days=1)).strftime("%Y-%m-%d")
        assert oh.availability_state(
            **self.HOURS, holiday_until=until, now=tuesday
        ) == oh.HOLIDAY

    def test_holiday_that_ended_yesterday_does_not_leak(self):
        today = weekday_at(1, 11)
        until = (today - timedelta(days=1)).strftime("%Y-%m-%d")
        assert oh.availability_state(
            **self.HOURS, holiday_until=until, now=today
        ) == oh.OPEN

    def test_holiday_outranks_weekly_off_so_the_message_is_right(self):
        # "Aaj chhutti hai" is more useful than "band hai" when both apply.
        monday = weekday_at(0, 11)
        until = monday.strftime("%Y-%m-%d")
        assert oh.availability_state(
            **self.HOURS, closed_days="Monday", holiday_until=until, now=monday
        ) == oh.HOLIDAY

    def test_missing_hours_never_hide_a_clinic(self):
        # The important regression: a data-entry gap must not delete a partner
        # from the directory. Unknown availability == available, not closed.
        assert oh.availability_state(now=weekday_at(0, 3)) == oh.OPEN

    def test_same_open_and_close_is_treated_as_unset(self):
        assert oh.availability_state(
            open_time="10:00", close_time="10:00", now=weekday_at(0, 15)
        ) == oh.OPEN

    def test_non_partner_is_directory_not_open(self):
        assert oh.availability_state(
            **self.HOURS, now=weekday_at(0, 11), is_partner=False
        ) == oh.DIRECTORY

    def test_overnight_window_covers_late_night(self):
        # A night clinic 22:00 → 02:00 must be open at 23:30 and at 01:00.
        assert oh.availability_state(
            open_time="22:00", close_time="02:00", now=weekday_at(0, 23) + timedelta(minutes=30)
        ) == oh.OPEN
        assert oh.availability_state(
            open_time="22:00", close_time="02:00", now=weekday_at(0, 1)
        ) == oh.OPEN
        # …and closed at 03:00.
        assert oh.availability_state(
            open_time="22:00", close_time="02:00", now=weekday_at(0, 3)
        ) == oh.CLOSED


class TestWithinHours:
    """The 🟢 filter uses schedule-only truth, independent of tier."""

    def test_directory_clinic_can_still_be_open_by_schedule(self):
        assert oh.within_hours(
            open_time="09:00", close_time="18:00", now=weekday_at(0, 11)
        )

    def test_closed_day_fails_the_filter(self):
        assert not oh.within_hours(
            open_time="09:00", close_time="18:00", closed_days="Monday",
            now=weekday_at(0, 11),
        )

    def test_no_hours_counts_as_open_for_filtering(self):
        assert oh.within_hours(now=weekday_at(0, 3))


class TestOpenNowAndNextOpening:
    def test_is_open_now_matches_the_state(self):
        assert oh.is_open_now(open_time="09:00", close_time="18:00", now=weekday_at(0, 11))
        assert not oh.is_open_now(open_time="09:00", close_time="18:00", now=weekday_at(0, 20))

    def test_closing_soon_still_counts_as_open(self):
        now = weekday_at(0, 17) + timedelta(minutes=30)
        assert oh.is_open_now(open_time="09:00", close_time="18:00", now=now)

    def test_next_opening_today_when_before_hours(self):
        assert oh.next_opening(
            open_time="09:00", close_time="18:00", now=weekday_at(0, 7)
        ) == "Aaj 09:00"

    def test_next_opening_tomorrow_when_after_hours(self):
        assert oh.next_opening(
            open_time="09:00", close_time="18:00", now=weekday_at(0, 20)
        ) == "Kal 09:00"

    def test_next_opening_skips_a_closed_day(self):
        # Monday 20:00, closed Sundays only → next is Tuesday 09:00.
        tomorrow = weekday_at(0, 20) + timedelta(days=1)
        assert oh.next_opening(
            open_time="09:00", close_time="18:00", now=weekday_at(0, 20)
        ).startswith("Kal")
        assert tomorrow.weekday() == 1

    def test_next_opening_empty_when_hours_unknown(self):
        assert oh.next_opening(now=weekday_at(0, 20)) == ""

    def test_minutes_until_close_counts_down(self):
        now = weekday_at(0, 17) + timedelta(minutes=15)
        assert oh.minutes_until_close("09:00", "18:00", now=now) == 45

    def test_minutes_until_close_is_none_when_shut(self):
        assert oh.minutes_until_close("09:00", "18:00", now=weekday_at(0, 20)) is None


class TestClosingNote:
    def test_open_note_states_the_time(self):
        note = oh.closing_note("09:00", "18:00", now=weekday_at(0, 11))
        assert "18:00" in note

    def test_closing_soon_note_counts_minutes(self):
        now = weekday_at(0, 17) + timedelta(minutes=40)
        note = oh.closing_note("09:00", "18:00", now=now)
        assert "20 min" in note

    def test_closed_note_points_at_the_next_opening(self):
        note = oh.closing_note("09:00", "18:00", now=weekday_at(0, 20))
        assert note.startswith("Kal 09:00")

    def test_unknown_hours_produce_no_note(self):
        assert oh.closing_note(None, None) == ""


class TestPublicDict:
    def test_shape_is_json_safe_and_complete(self):
        data = oh.to_public_dict(
            open_time="09:00", close_time="18:00", now=weekday_at(0, 11)
        )
        assert data["state"] == oh.OPEN
        assert data["is_open"] is True
        assert data["hours"] == "09:00 – 18:00"
        assert data["open_time"] == "09:00"
        assert data["close_time"] == "18:00"
        assert data["badge"].startswith("🟢")
        assert data["next_opening"] == ""

    def test_labels_are_hinglish_and_present_for_every_state(self):
        for state in (oh.OPEN, oh.CLOSING_SOON, oh.CLOSED, oh.HOLIDAY, oh.DIRECTORY):
            assert oh.availability_label(state)
            assert oh.availability_badge(state)

    def test_unknown_state_falls_back_to_directory_wording(self):
        assert oh.availability_label("WHATEVER") == oh.AVAILABILITY_LABEL[oh.DIRECTORY]


# ══════════════════════════════════════════════════════════════════════════
# 2. travel — "should I leave now?"
# ══════════════════════════════════════════════════════════════════════════


class TestDistance:
    def test_known_distance_is_approximately_right(self):
        # Jodhpur → Jaipur is ~290 km as the crow flies.
        km = travel.haversine_km(26.2389, 73.0243, 26.9124, 75.7873)
        assert 270 < km < 310

    def test_same_point_is_zero(self):
        assert travel.haversine_km(26.2389, 73.0243, 26.2389, 73.0243) == pytest.approx(0, abs=1e-6)

    def test_missing_coordinates_give_none(self):
        assert travel.distance_km(None, None, 26.2, 73.0) is None
        assert travel.distance_km(26.2, 73.0, None, None) is None

    def test_zero_zero_placeholder_is_not_a_real_location(self):
        # The classic "no GPS fix" default must not be read as a coordinate.
        assert travel.distance_km(0.0, 0.0, 26.2389, 73.0243) is None
        assert travel.distance_km(26.2389, 73.0243, 0.0, 0.0) is None

    def test_junk_coordinates_give_none(self):
        assert travel.distance_km("abc", "xyz", 26.2, 73.0) is None


class TestTravelMinutes:
    def test_short_hop_includes_the_doorstep_buffer(self):
        # 3 km at 18 km/h = 10 min, plus the 8 min buffer.
        assert travel.travel_minutes(3.0) == 18

    def test_no_distance_gives_none(self):
        assert travel.travel_minutes(None) is None

    def test_absurd_distance_is_refused_rather_than_guessed(self):
        assert travel.travel_minutes(5000) is None

    def test_zero_distance_still_costs_the_buffer(self):
        assert travel.travel_minutes(0) == travel.DEFAULT_BUFFER_MINUTES


class TestLeaveDecision:
    def test_plenty_of_time_means_wait(self):
        d = travel.leave_decision(wait_minutes=40, travel=10)
        assert d["should_leave"] is False
        assert d["urgency"] == "wait"
        assert d["slack_minutes"] == 30

    def test_tight_timing_means_leave_now(self):
        d = travel.leave_decision(wait_minutes=14, travel=10)
        assert d["should_leave"] is True
        assert d["urgency"] == "now"

    def test_already_late_is_told_the_truth(self):
        d = travel.leave_decision(wait_minutes=6, travel=25)
        assert d["urgency"] == "late"
        assert d["should_leave"] is True

    def test_without_coordinates_it_falls_back_to_wait_only(self):
        d = travel.leave_decision(wait_minutes=12, travel=None)
        assert d["has_travel"] is False
        assert d["should_leave"] is True  # old behaviour: <= 15 min
        assert d["slack_minutes"] is None

    def test_no_travel_and_long_wait_does_not_say_leave(self):
        d = travel.leave_decision(wait_minutes=60, travel=None)
        assert d["should_leave"] is False


class TestDepartureMessage:
    def test_without_travel_it_keeps_the_old_wording(self):
        msg = travel.departure_message(token=14, wait_minutes=20)
        assert "Token #14" in msg
        assert "reception" in msg

    def test_with_travel_it_advises_when_to_leave(self):
        msg = travel.departure_message(token=7, wait_minutes=45, travel=12)
        assert "Token #7" in msg
        assert "12 min" in msg

    def test_late_case_is_honest_not_reassuring(self):
        msg = travel.departure_message(token=9, wait_minutes=5, travel=30)
        assert "late" in msg.lower()

    def test_never_raises_on_junk(self):
        for token, wait, dist in [(None, None, None), ("x", "y", "z"), (1, -5, -9)]:
            assert isinstance(travel.departure_message(token, wait, dist), str)


# ══════════════════════════════════════════════════════════════════════════
# 3. E-07 — no-show detection
# ══════════════════════════════════════════════════════════════════════════


NOW = datetime(2026, 10, 2, 12, 0)
TZ_NOW = NOW.replace(tzinfo=timezone.utc)


def _entry(status: str, called_minutes_ago: float | None, token: int = 1):
    """A dict-shaped queue entry — ewt accepts dicts or ORM rows alike."""
    called_at = (
        TZ_NOW - timedelta(minutes=called_minutes_ago)
        if called_minutes_ago is not None
        else None
    )
    return {
        "id": f"e{token}",
        "status": status,
        "called_at": called_at,
        "token_number": token,
    }


class TestNoShow:
    def test_called_and_absent_past_the_threshold_is_a_no_show(self):
        assert ewt.is_no_show(_entry("CALLED", 9), now=TZ_NOW) is True

    def test_called_a_moment_ago_is_not_yet_a_no_show(self):
        assert ewt.is_no_show(_entry("CALLED", 3), now=TZ_NOW) is False

    def test_exactly_at_the_threshold_counts(self):
        assert ewt.is_no_show(_entry("CALLED", 8), now=TZ_NOW) is True

    def test_waiting_patient_is_never_swept(self):
        # They were never summoned — leaving them waiting is not their fault.
        assert ewt.is_no_show(_entry("WAITING", 60), now=TZ_NOW) is False

    def test_hold_is_untouched_because_e02_already_protects_them(self):
        assert ewt.is_no_show(_entry("HOLD", 60), now=TZ_NOW) is False

    def test_patient_inside_the_chamber_is_present(self):
        assert ewt.is_no_show(_entry("IN_PROGRESS", 60), now=TZ_NOW) is False

    def test_missing_called_at_does_not_punish_an_unknown(self):
        assert ewt.is_no_show(_entry("CALLED", None), now=TZ_NOW) is False

    def test_none_entry_is_safe(self):
        assert ewt.is_no_show(None, now=TZ_NOW) is False

    def test_threshold_is_configurable(self):
        assert ewt.is_no_show(_entry("CALLED", 4), now=TZ_NOW, threshold=3) is True


class TestSweep:
    def test_splits_todays_queue_preserving_order(self):
        rows = [
            _entry("WAITING", None, 1),
            _entry("CALLED", 12, 2),
            _entry("IN_PROGRESS", None, 3),
            _entry("CALLED", 20, 4),
            _entry("HOLD", 30, 5),
        ]
        absent, present = ewt.sweep_no_shows(rows, now=TZ_NOW)
        assert [e["token_number"] for e in absent] == [2, 4]
        assert [e["token_number"] for e in present] == [1, 3, 5]

    def test_nothing_swept_when_everyone_is_present(self):
        rows = [_entry("WAITING", None, 1), _entry("IN_PROGRESS", None, 2)]
        absent, present = ewt.sweep_no_shows(rows, now=TZ_NOW)
        assert absent == []
        assert len(present) == 2

    def test_empty_queue_is_safe(self):
        assert ewt.sweep_no_shows([], now=TZ_NOW) == ([], [])
        assert ewt.sweep_no_shows(None, now=TZ_NOW) == ([], [])

    def test_removing_a_no_show_lowers_everybody_elses_wait(self):
        """The whole point of E-07: an absent patient must not inflate the EWT."""
        ahead = [_entry("CALLED", 30, 2), _entry("WAITING", None, 3)]
        before = ewt.estimate_wait(ahead=ahead, avg_minutes=10, samples=30, chamber_open=True)
        _absent, remaining = ewt.sweep_no_shows(ahead, now=TZ_NOW)
        after = ewt.estimate_wait(ahead=remaining, avg_minutes=10, samples=30, chamber_open=True)
        assert after.patients_ahead < before.patients_ahead
        assert after.minutes < before.minutes

    def test_recovery_note_names_the_token(self):
        note = ewt.no_show_recovery_note(14, 11.4)
        assert "#14" in note
        assert "11 min" in note


class TestMinutesSinceCalled:
    def test_none_when_never_called(self):
        assert ewt.minutes_since_called(_entry("WAITING", None)) is None

    def test_zero_is_distinct_from_never_called(self):
        assert ewt.minutes_since_called(_entry("CALLED", 0), now=TZ_NOW) == pytest.approx(0.0)

    def test_counts_forward(self):
        assert ewt.minutes_since_called(_entry("CALLED", 6.5), now=TZ_NOW) == pytest.approx(6.5)


# ══════════════════════════════════════════════════════════════════════════
# 4. API contract — the marketplace must expose real availability
# ══════════════════════════════════════════════════════════════════════════


def _make_clinic(
    code: str,
    name: str,
    *,
    open_time: str = "09:00",
    close_time: str = "18:00",
    closed_days: str = "",
    holiday_until: str = "",
    license_active: bool = True,
    lat: float | None = None,
    lon: float | None = None,
    rating: float | None = None,
    rating_count: int = 0,
    doctor: str | None = None,
) -> str:
    """Insert a clinic and return its id as a string."""
    import asyncio

    from src.shared.domain.base_entity import uuid7

    clinic_id = uuid7()

    async def _insert():
        async with async_session_factory() as session:
            session.add(
                ClinicModel(
                    id=clinic_id,
                    clinic_name=name,
                    clinic_code=code,
                    doctor_name=doctor or f"Dr {name}",
                    specialty="Cardiology",
                    city="Jodhpur",
                    state="Rajasthan",
                    latitude=lat,
                    longitude=lon,
                    open_time=open_time,
                    close_time=close_time,
                    closed_days=closed_days,
                    holiday_until=holiday_until,
                    rating=rating,
                    rating_count=rating_count,
                    is_license_active=license_active,
                    is_active=True,
                )
            )
            await session.commit()
        return str(clinic_id)

    return asyncio.run(_insert())


@pytest.fixture(scope="module")
def client():
    """Plain TestClient — no lifespan, so no schedulers or backup threads run."""
    return TestClient(main_v2.app)


def _doctors(client, **params) -> dict:
    response = client.get("/api/v1/marketplace/doctors", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def _find(payload: dict, clinic_id: str) -> dict:
    for doctor in payload["doctors"]:
        if doctor["id"] == clinic_id:
            return doctor
    raise AssertionError(f"clinic {clinic_id} missing from the directory")


class TestMarketplaceAvailability:
    def test_availability_is_no_longer_a_constant(self, client):
        """Before BLOCK 2 every partner answered the literal string "OPEN"."""
        open_clinic = _make_clinic(
            "AVL-OPEN", "Always Open Clinic", open_time="00:01", close_time="23:58"
        )
        doctor = _find(_doctors(client, specialty="Cardiology"), open_clinic)
        assert doctor["availability"] in (oh.OPEN, oh.CLOSING_SOON)
        assert doctor["is_open_now"] is True
        assert doctor["hours"] == "00:01 – 23:58"

    def test_closed_day_shows_closed_regardless_of_the_hour(self, client):
        # Pin the state with a closed day (not the clock) so this cannot flake.
        today_number = str(oh.local_now().weekday())
        shut = _make_clinic("AVL-OFF", "Weekly Off Clinic", closed_days=today_number)
        doctor = _find(_doctors(client, specialty="Cardiology"), shut)
        assert doctor["availability"] == oh.CLOSED
        assert doctor["is_open_now"] is False
        assert doctor["next_opening"]

    def test_holiday_shows_chhutti(self, client):
        until = (oh.local_now().date() + timedelta(days=1)).isoformat()
        on_holiday = _make_clinic("AVL-HOL", "Holiday Clinic", holiday_until=until)
        doctor = _find(_doctors(client, specialty="Cardiology"), on_holiday)
        assert doctor["availability"] == oh.HOLIDAY
        assert "chhutti" in doctor["availability_label"].lower()

    def test_clinic_without_hours_stays_visible_and_available(self, client):
        # The regression that matters: missing hours must not hide a partner.
        bare = _make_clinic("AVL-BARE", "No Hours Clinic", open_time="", close_time="")
        doctor = _find(_doctors(client, specialty="Cardiology"), bare)
        assert doctor["availability"] == oh.OPEN
        assert doctor["hours"] == ""

    def test_rating_is_exposed(self, client):
        rated = _make_clinic("AVL-RATE", "Rated Clinic", rating=4.6, rating_count=37)
        doctor = _find(_doctors(client, specialty="Cardiology"), rated)
        assert doctor["rating"] == 4.6
        assert doctor["rating_count"] == 37


class TestOpenNowFilter:
    def test_filter_drops_the_clinics_that_are_shut_today(self, client):
        today_number = str(oh.local_now().weekday())
        _make_clinic(
            "FLT-OPEN", "Filter Open Clinic", open_time="00:01", close_time="23:58"
        )
        shut_id = _make_clinic("FLT-SHUT", "Filter Shut Clinic", closed_days=today_number)

        payload = _doctors(client, specialty="Cardiology", open_now="true")
        ids = [d["id"] for d in payload["doctors"]]
        assert shut_id not in ids
        assert all(d["within_hours"] for d in payload["doctors"])

    def test_filter_preserves_a_genuinely_open_directory_clinic(self, client):
        """A Tier-2 clinic open at 4 PM must not vanish from an "open now" search."""
        tier_two = _make_clinic(
            "FLT-T2", "Directory Open Clinic",
            open_time="00:01", close_time="23:58", license_active=False,
        )
        payload = _doctors(client, specialty="Cardiology", open_now="true")
        ids = [d["id"] for d in payload["doctors"]]
        assert tier_two in ids
        # …but it still advertises itself honestly as a directory listing.
        assert _find(payload, tier_two)["availability"] == oh.DIRECTORY

    def test_without_the_filter_the_closed_clinic_is_still_listed(self, client):
        today_number = str(oh.local_now().weekday())
        shut_id = _make_clinic("FLT-VIS", "Visible When Shut", closed_days=today_number)
        payload = _doctors(client, specialty="Cardiology")
        assert shut_id in [d["id"] for d in payload["doctors"]]

    def test_counts_are_reported(self, client):
        payload = _doctors(client, specialty="Cardiology", open_now="true")
        assert payload["open_now"] == sum(1 for d in payload["doctors"] if d["is_open_now"])
        assert payload["total"] == len(payload["doctors"])


class TestSorting:
    def test_two_tier_ranking_survives_every_sort(self, client):
        """Partners must stay above directory listings — the documented rule."""
        _make_clinic(
            "SRT-T2", "Zzz Directory Clinic",
            open_time="00:01", close_time="23:58", license_active=False,
        )
        for sort in ("smart", "distance", "wait", "rating", "name"):
            payload = _doctors(client, specialty="Cardiology", sort=sort)
            tiers = [d["tier"] for d in payload["doctors"]]
            assert tiers == sorted(tiers), f"tier order broke for sort={sort}"

    def test_sort_by_distance_orders_near_first(self, client):
        _make_clinic(
            "SRT-NEAR", "Near Clinic",
            open_time="00:01", close_time="23:58", lat=26.2400, lon=73.0250,
        )
        _make_clinic(
            "SRT-FAR", "Far Clinic",
            open_time="00:01", close_time="23:58", lat=26.9124, lon=75.7873,
        )
        payload = _doctors(client, specialty="Cardiology", sort="distance", lat=26.2389, lon=73.0243)
        distances = [d["distance_km"] for d in payload["doctors"] if d["distance_km"] is not None]
        assert distances == sorted(distances)
        assert distances[0] < 5  # the near clinic is genuinely near

    def test_distance_is_null_without_patient_coordinates(self, client):
        clinic = _make_clinic(
            "SRT-NOLOC", "No Patient Location Clinic",
            open_time="00:01", close_time="23:58", lat=26.2400, lon=73.0250,
        )
        doctor = _find(_doctors(client, specialty="Cardiology"), clinic)
        assert doctor["distance_km"] is None

    def test_sort_by_rating_orders_best_first(self, client):
        _make_clinic("SRT-R5", "Five Star Clinic", rating=4.9, rating_count=10,
                     open_time="00:01", close_time="23:58")
        _make_clinic("SRT-R3", "Three Star Clinic", rating=3.1, rating_count=10,
                     open_time="00:01", close_time="23:58")
        payload = _doctors(client, specialty="Cardiology", sort="rating")
        ratings = [d["rating"] for d in payload["doctors"] if d["rating"] is not None]
        assert ratings == sorted(ratings, reverse=True)

    def test_sort_by_name_is_alphabetical_within_a_tier(self, client):
        payload = _doctors(client, specialty="Cardiology", sort="name")
        names = [d["doctor_name"].lower() for d in payload["doctors"] if d["tier"] == 1]
        assert names == sorted(names)

    def test_unknown_sort_falls_back_to_smart_instead_of_failing(self, client):
        payload = _doctors(client, specialty="Cardiology", sort="banana")
        assert payload["sort"] == "smart"

    def test_unrated_and_unlocated_clinics_sort_last_not_crash(self, client):
        """None must never be compared against a number."""
        _make_clinic("SRT-NONE", "Unrated Unlocated Clinic",
                     open_time="00:01", close_time="23:58")
        for sort in ("distance", "rating", "wait", "smart"):
            response = client.get(
                "/api/v1/marketplace/doctors",
                params={"specialty": "Cardiology", "sort": sort},
            )
            assert response.status_code == 200, f"sort={sort} → {response.status_code}"


# ══════════════════════════════════════════════════════════════════════════
# 5. Queue-engine routes — E-07 sweep, recall, and the GPS-aware alert
# ══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def opd_doctor(monkeypatch):
    """Pretend a chief doctor is logged into the OPD dashboard."""
    from src.presentation.opd.routes import opd_routes

    monkeypatch.setattr(
        opd_routes,
        "_require_opd_session",
        lambda request: {
            "role": "chief",
            "doctor_id": "chief",
            "name": "Dr Test",
            "lic_info": {},
        },
    )
    return "chief"


def _make_entry(
    clinic_id: str,
    token: int,
    status: str = "WAITING",
    patient_name: str = "Patient",
    called_minutes_ago: float | None = None,
    patient_id: str | None = None,
) -> str:
    """Insert a live OPD queue entry and return its id."""
    import asyncio
    from datetime import timezone as _tz

    from src.infrastructure.queue.models.queue_entry_model import QueueEntryModel
    from src.shared.domain.base_entity import uuid7

    entry_id = uuid7()
    now = datetime.now(_tz.utc)
    called_at = (
        now - timedelta(minutes=called_minutes_ago)
        if called_minutes_ago is not None
        else None
    )
    pid = patient_id or f"AV-{token}"

    async def _insert():
        async with async_session_factory() as session:
            session.add(
                QueueEntryModel(
                    id=entry_id,
                    clinic_id=clinic_id,
                    doctor_id="chief",
                    visit_id=f"VIS-AVL-{token}",
                    patient_id=pid,
                    patient_uuid=str(uuid7()),
                    patient_name=patient_name,
                    service_code="OPD",
                    token_number=token,
                    department="Cardiology",
                    room="OPD Room",
                    status=status,
                    priority=0,
                    display_order=0,
                    sort_key=float(token),
                    visit_type="followup",
                    complexity_weight=1,
                    called_at=called_at,
                    created_by="test",
                    updated_by="test",
                    version=1,
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.commit()

    asyncio.run(_insert())
    return str(entry_id)


async def _entry_status(entry_id: str) -> str:
    """Read an entry's status straight from the database."""
    import uuid as _uuid

    from src.infrastructure.queue.models.queue_entry_model import QueueEntryModel

    async with async_session_factory() as session:
        row = await session.get(QueueEntryModel, _uuid.UUID(entry_id))
        return (row.status or "") if row else ""


class TestNoShowSweepRoute:
    def test_called_and_absent_is_marked_no_show(self, client, opd_doctor):
        clinic = _make_clinic("NS-A", "No Show Clinic")
        stale = _make_entry(clinic, 1, status="CALLED", called_minutes_ago=20,
                            patient_name="Absent")
        fresh = _make_entry(clinic, 2, status="CALLED", called_minutes_ago=1,
                            patient_name="Walking In")

        body = client.post("/opd/api/queue/sweep-no-shows", json={}).json()
        assert body["ok"] is True
        marked_ids = [m["entry_id"] for m in body["marked"]]
        assert stale in marked_ids
        assert fresh not in marked_ids
        assert body["count"] == len(marked_ids)

        import asyncio

        assert asyncio.run(_entry_status(stale)) == "NO_SHOW"
        assert asyncio.run(_entry_status(fresh)) == "CALLED"

    def test_sweep_is_idempotent(self, client, opd_doctor):
        clinic = _make_clinic("NS-B", "Idempotent Clinic")
        _make_entry(clinic, 1, status="CALLED", called_minutes_ago=30)

        first = client.post("/opd/api/queue/sweep-no-shows", json={}).json()
        second = client.post("/opd/api/queue/sweep-no-shows", json={}).json()
        assert first["count"] >= 1
        # Already swept → nothing left to sweep, so nobody is double-counted.
        assert second["count"] == 0

    def test_waiting_patients_are_never_swept_by_the_route(self, client, opd_doctor):
        clinic = _make_clinic("NS-C", "Waiting Clinic")
        waiting = _make_entry(clinic, 1, status="WAITING", patient_name="Patiently Waiting")
        body = client.post("/opd/api/queue/sweep-no-shows", json={}).json()
        assert waiting not in [m["entry_id"] for m in body["marked"]]

        import asyncio

        assert asyncio.run(_entry_status(waiting)) == "WAITING"

    def test_threshold_can_be_raised_to_protect_a_slow_walk(self, client, opd_doctor):
        clinic = _make_clinic("NS-D", "Threshold Clinic")
        recent = _make_entry(clinic, 1, status="CALLED", called_minutes_ago=6)
        body = client.post(
            "/opd/api/queue/sweep-no-shows", json={"threshold_minutes": 30}
        ).json()
        assert body["threshold_minutes"] == 30
        assert recent not in [m["entry_id"] for m in body["marked"]]

    def test_recovery_note_names_the_token(self, client, opd_doctor):
        clinic = _make_clinic("NS-E", "Note Clinic")
        _make_entry(clinic, 7, status="CALLED", called_minutes_ago=15)
        body = client.post("/opd/api/queue/sweep-no-shows", json={}).json()
        marked = [m for m in body["marked"] if m["token_number"] == 7]
        assert marked, "token 7 should have been swept"
        assert "#7" in marked[0]["note"]


class TestLiveFeedSweepsAutomatically:
    def test_queue_ewt_removes_the_absent_without_anyone_clicking(self, client, opd_doctor):
        """The countdown must be honest even if the doctor taps nothing."""
        clinic = _make_clinic("NS-F", "Auto Sweep Clinic")
        stale = _make_entry(clinic, 1, status="CALLED", called_minutes_ago=25,
                            patient_name="Never Came")
        _make_entry(clinic, 2, status="WAITING", patient_name="Still Here")

        feed = client.get("/opd/api/queue-ewt").json()
        assert feed["ok"] is True
        assert feed["counts"]["no_show"] >= 1
        assert stale not in [row["entry_id"] for row in feed["queue"]]

    def test_feed_reports_the_absence_for_the_reception(self, client, opd_doctor):
        clinic = _make_clinic("NS-G", "Report Clinic")
        _make_entry(clinic, 3, status="CALLED", called_minutes_ago=40,
                    patient_name="Gone Home")
        feed = client.get("/opd/api/queue-ewt").json()
        rows = [r for r in feed["no_shows"] if r["token_number"] == 3]
        assert rows
        assert rows[0]["waited_minutes"] >= 8
        assert "wapas" in rows[0]["note"].lower()


class TestRecall:
    def test_a_no_show_can_be_brought_back_into_the_line(self, client, opd_doctor):
        clinic = _make_clinic("RC-A", "Recall Clinic")
        late = _make_entry(clinic, 1, status="CALLED", called_minutes_ago=20,
                           patient_name="Stuck In Traffic")
        client.post("/opd/api/queue/sweep-no-shows", json={})

        body = client.post(
            "/opd/api/queue/recall", json={"entry_id": late}
        ).json()
        assert body["ok"] is True
        assert body["token"] == 1

        import asyncio

        assert asyncio.run(_entry_status(late)) == "WAITING"

    def test_recall_puts_them_at_the_back_by_default(self, client, opd_doctor):
        clinic = _make_clinic("RC-B", "Fair Clinic")
        _make_entry(clinic, 1, status="WAITING", patient_name="Already Waiting")
        late = _make_entry(clinic, 2, status="CALLED", called_minutes_ago=20,
                           patient_name="Late Arrival")
        client.post("/opd/api/queue/sweep-no-shows", json={})

        body = client.post("/opd/api/queue/recall", json={"entry_id": late}).json()
        assert body["patients_ahead"] >= 1, "someone who showed up on time must stay ahead"
        assert "aakhir" in body["position_note"]

    def test_a_present_patient_cannot_be_recalled(self, client, opd_doctor):
        clinic = _make_clinic("RC-C", "Guard Clinic")
        waiting = _make_entry(clinic, 1, status="WAITING")
        body = client.post("/opd/api/queue/recall", json={"entry_id": waiting}).json()
        assert body["ok"] is False
        assert body["error"]

    def test_recall_needs_an_entry_id(self, client, opd_doctor):
        response = client.post("/opd/api/queue/recall", json={})
        assert response.status_code == 400


class TestLeaveNowWithTravel:
    def test_without_coordinates_it_still_answers(self, client, opd_doctor):
        clinic = _make_clinic("LN-A", "No GPS Clinic",
                              lat=26.2389, lon=73.0243, open_time="00:01", close_time="23:58")
        entry = _make_entry(clinic, 1, status="WAITING")
        body = client.post("/opd/api/queue/leave-now", json={"entry_id": entry}).json()
        assert body["ok"] is True
        assert body["has_travel"] is False
        assert body["travel_minutes"] is None
        assert isinstance(body["message"], str) and body["message"]

    def test_patient_coordinates_add_a_travel_estimate(self, client, opd_doctor):
        clinic = _make_clinic("LN-B", "GPS Clinic",
                              lat=26.2389, lon=73.0243, open_time="00:01", close_time="23:58")
        entry = _make_entry(clinic, 1, status="WAITING")
        # ~7 km across the same city — the case the feature exists for.
        body = client.post(
            "/opd/api/queue/leave-now",
            json={"entry_id": entry, "patient_lat": 26.30, "patient_lon": 73.05},
        ).json()
        assert body["ok"] is True
        assert body["has_travel"] is True
        assert 5 < body["distance_km"] < 10
        assert 25 < body["travel_minutes"] < 45

    def test_an_impossibly_distant_patient_gets_no_fake_estimate(self, client, opd_doctor):
        """285 km away is a different city, not a commute — say nothing."""
        clinic = _make_clinic("LN-E", "Same City Clinic",
                              lat=26.2389, lon=73.0243, open_time="00:01", close_time="23:58")
        entry = _make_entry(clinic, 1, status="WAITING")
        body = client.post(
            "/opd/api/queue/leave-now",
            json={"entry_id": entry, "patient_lat": 26.9124, "patient_lon": 75.7873},
        ).json()
        assert body["has_travel"] is False
        assert body["travel_minutes"] is None
        # …and the patient still gets a usable message rather than an error.
        assert "reception" in body["message"]

    def test_explicit_travel_minutes_win_over_gps(self, client, opd_doctor):
        clinic = _make_clinic("LN-C", "Explicit Clinic",
                              lat=26.2389, lon=73.0243, open_time="00:01", close_time="23:58")
        entry = _make_entry(clinic, 1, status="WAITING")
        body = client.post(
            "/opd/api/queue/leave-now",
            json={"entry_id": entry, "travel_minutes": 12,
                  "patient_lat": 26.9124, "patient_lon": 75.7873},
        ).json()
        assert body["travel_minutes"] == 12

    def test_urgency_is_reported_for_the_ui(self, client, opd_doctor):
        clinic = _make_clinic("LN-D", "Urgency Clinic",
                              lat=26.2389, lon=73.0243, open_time="00:01", close_time="23:58")
        entry = _make_entry(clinic, 1, status="WAITING")
        body = client.post(
            "/opd/api/queue/leave-now",
            json={"entry_id": entry, "travel_minutes": 5},
        ).json()
        assert body["urgency"] in ("wait", "soon", "now", "late")

    def test_unknown_entry_is_a_clean_404(self, client, opd_doctor):
        response = client.post(
            "/opd/api/queue/leave-now",
            json={"entry_id": "00000000-0000-0000-0000-000000000000"},
        )
        assert response.status_code == 404
        assert response.json()["ok"] is False
