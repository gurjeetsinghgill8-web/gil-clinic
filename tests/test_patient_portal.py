"""Patient Portal (Smart OPD) tests — v1.0

Covers:
  * metric catalog + flagging + Hinglish guidance
  * pivot (BP 135/85 ek column) + custom fields alag series
  * SVG chart (2+ points), HTML/CSV/PDF report builders (graphs file ke andar)
  * public portal: token → verify → readings save → charts/table
  * "Doctor ko bhejo": share link banao → koi bhi (bina login) khol sake → READ-ONLY
  * expiry: 7 din baad `/s/<token>` 410; aur `/s/` par koi write endpoint nahi

Run:  python -m pytest tests/test_patient_portal.py -q
"""

from __future__ import annotations

import datetime as dt
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_TEST_DB = ROOT / "test_patient_portal.db"
if _TEST_DB.exists():
    try:
        _TEST_DB.unlink()
    except Exception:
        pass

os.environ["GHOS_DB_URL"] = f"sqlite:///{_TEST_DB}"
os.environ["SYSTEM_AI_FALLBACK_ENABLED"] = "false"

import sqlalchemy as sa  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import main_v2  # noqa: E402
from src.infrastructure.opd.models.patient_portal_models import (  # noqa: E402
    PatientReadingModel,
    PatientShareModel,
)
from src.infrastructure.patient.models.patient_model import PatientModel  # noqa: E402
from src.presentation.opd.routes.opd_routes import _create_opd_session  # noqa: E402
from src.utils import patient_tokens as tk  # noqa: E402
from src.utils.patient_chart_svg import trend_chart_svg, trend_point_count  # noqa: E402
from src.utils.patient_metrics import (  # noqa: E402
    build_series,
    flag_reading,
    guidance_for,
    metric_by_code,
    pivot_readings,
)
from src.utils.patient_report import (  # noqa: E402
    build_report_csv,
    build_report_html,
    build_report_pdf,
)

PID = "GIL-TEST-001"
PNAME = "Raj Kumar"
PHONE = "9876543210"


# ── helpers ──────────────────────────────────────────────────────────────────
def _reading(code: str, label: str, unit: str, value: float, day: int, status: str = "ok") -> dict:
    return {
        "reading_id": f"{code}-{day}",
        "patient_id": PID,
        "code": code,
        "label": label,
        "unit": unit,
        "value": value,
        "date_time": dt.datetime(2026, 9, day, 8, 0).isoformat(),
        "source": "patient",
        "status": status,
    }


SAMPLE = [
    _reading("bp-systolic", "BP Systolic", "mmHg", 138, 1),
    _reading("bp-diastolic", "BP Diastolic", "mmHg", 88, 1),
    _reading("bp-systolic", "BP Systolic", "mmHg", 152, 3, "high"),
    _reading("bp-diastolic", "BP Diastolic", "mmHg", 96, 3, "high"),
    _reading("bp-systolic", "BP Systolic", "mmHg", 146, 6, "high"),
    _reading("bp-diastolic", "BP Diastolic", "mmHg", 92, 6, "high"),
    _reading("pulse", "Pulse", "bpm", 82, 1),
    _reading("pulse", "Pulse", "bpm", 88, 6),
    _reading("rbs", "Blood Sugar (RBS)", "mg/dL", 148, 1, "high"),
    _reading("custom", "Hemoglobin", "g/dL", 12.4, 1),
    _reading("custom", "Hemoglobin", "g/dL", 12.9, 6),
]


def _doctor_client() -> TestClient:
    client = TestClient(main_v2.app)
    client.cookies.set("opd_session", _create_opd_session("chief", "chief", "Dr Test"))
    return client


def _ensure_patient() -> None:
    """Patient row seed (sync engine — TestClient ke saath loop conflict nahi)."""
    main_v2.Base.metadata.create_all(bind=main_v2.engine)
    with main_v2.SessionLocal() as session:
        existing = session.execute(
            sa.select(PatientModel).where(PatientModel.patient_id == PID)
        ).scalar_one_or_none()
        if existing is None:
            session.add(
                PatientModel(
                    patient_id=PID,
                    name=PNAME,
                    age=58,
                    gender="M",
                    phone=PHONE,
                    phone_hash=tk.phone_hash(PHONE),
                )
            )
            session.commit()


# ── 1. metric engine ─────────────────────────────────────────────────────────
def test_metric_flagging_and_guidance():
    bp = metric_by_code("bp-systolic")
    assert flag_reading(bp, 120) == "ok"
    assert flag_reading(bp, 152) == "high"
    assert flag_reading(bp, 190) == "critical"
    assert flag_reading(bp, 70) == "critical"  # 80 se neeche = critical
    assert flag_reading(metric_by_code("unknown-metric"), 10) == "ok"
    assert "140/90" in guidance_for(bp, "high")
    assert guidance_for(bp, "critical").lower().startswith("khatarnak")


def test_series_and_pivot_shape():
    series = build_series(SAMPLE)
    codes = [s["code"] for s in series]
    assert "bp-systolic" in codes and "custom:Hemoglobin" in codes
    # custom fields label-wise alag (pehle sab ek hi graph me mil jate the)
    assert len([c for c in codes if c.startswith("custom:")]) == 1
    pivot = pivot_readings(SAMPLE)
    labels = [c["label"] for c in pivot["columns"]]
    assert labels[0] == "BP" and "Hemoglobin" in labels
    first_row = pivot["rows"][0]
    assert first_row["cells"][0]["text"] == "146/92"  # BP ek column me
    assert first_row["cells"][0]["status"] == "high"


# ── 2. reports (graphs file ke andar) ────────────────────────────────────────
def test_chart_requires_two_points():
    assert trend_chart_svg([120], ["2026-09-01T08:00:00"]) == ""
    assert trend_point_count([1, None, 3]) == 2
    svg = trend_chart_svg([138, 152, 146], ["2026-09-01", "2026-09-03", "2026-09-06"], unit="mmHg",
                          normal_min=90, normal_max=140)
    assert 'class="trend-chart"' in svg
    assert svg.count("<polyline") == 2  # halo + line
    assert 'fill="#10b981"' in svg  # normal range band
    assert "320" in svg and "160" in svg


def test_html_report_embeds_graphs():
    html = build_report_html(
        {
            "patient_name": PNAME,
            "patient_id": PID,
            "readings": SAMPLE,
            "mode": "shared",
            "note": "BP 3 din se high hai",
        }
    )
    assert html.count('class="trend-chart"') >= 3
    assert "Graphs — trend" in html
    assert "Patient ne khud share kiya" in html
    assert "BP 3 din se high hai" in html
    assert "undefined" not in html


def test_csv_and_pdf_reports():
    csv_text = build_report_csv(SAMPLE)
    assert csv_text.splitlines()[0].startswith('Date & time,BP')
    assert len(csv_text.splitlines()) >= 4
    pdf = build_report_pdf(
        {"patient_name": PNAME, "patient_id": PID, "readings": SAMPLE, "mode": "patient"}
    )
    assert pdf[:5] == b"%PDF-"
    assert len(pdf) > 2000
    # graph wali PDF me asli drawing content hota hai — 1-reading wali se badi file
    one_point = build_report_pdf(
        {"patient_name": PNAME, "patient_id": PID, "readings": SAMPLE[:1], "mode": "patient"}
    )
    assert len(pdf) > len(one_point), f"charts PDF me add nahi hue ({len(pdf)} vs {len(one_point)})"
    assert b"/Count 2" in pdf  # charts + table dono page par


# ── 3. doctor → patient link → patient portal ────────────────────────────────
def test_portal_link_and_patient_flow():
    _ensure_patient()
    with _doctor_client() as client:
        r = client.post("/opd/api/patient-link", json={"patient_id": PID})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["ok"] is True
        assert "/my/" in data["url"]
        assert "wa.me" in data["whatsapp_url"]
        token = data["token"]
        # dobara maangne par WAHI link milta hai (doctor ko har baar naya nahi bhejna padta)
        again = client.post("/opd/api/patient-link", json={"patient_id": PID}).json()
        assert again["token"] == token

    with TestClient(main_v2.app) as anon:
        # 1) link khulta hai — pehle verify screen
        page = anon.get(f"/my/{token}")
        assert page.status_code == 200
        assert "Suraksha Satyapan" in page.text
        # 2) data verification ke bina nahi milta
        assert anon.get(f"/my/{token}/data").status_code == 401
        # 3) galat number → 403
        bad = anon.post(f"/my/{token}/verify", json={"phone": "9999999999"})
        assert bad.status_code == 403
        # 4) sahi number → cookie + data
        good = anon.post(f"/my/{token}/verify", json={"phone": PHONE})
        assert good.status_code == 200 and good.json()["ok"] is True
        assert anon.get(f"/my/{token}/data").status_code == 200

        # 5) readings save
        saved = anon.post(
            f"/my/{token}/readings",
            json={
                "dateTime": dt.datetime(2026, 9, 10, 8, 0).isoformat(),
                "values": [
                    {"code": "bp-systolic", "value": 152},
                    {"code": "bp-diastolic", "value": 96},
                    {"code": "pulse", "value": 82},
                    {"code": "custom", "value": 12.4, "label": "Hemoglobin", "unit": "g/dL"},
                ],
            },
        )
        assert saved.status_code == 200, saved.text
        body = saved.json()
        assert body["ok"] and len(body["saved"]) == 4
        assert 'class="trend-chart"' not in body["trends"]  # pehli reading = koi line nahi
        assert "Hemoglobin" in body["table"]
        assert any(a["status"] == "high" for a in body["alerts"])  # 152/96 = high

        # 6) doosri reading ke baad graph ban jata hai
        anon.post(
            f"/my/{token}/readings",
            json={
                "dateTime": dt.datetime(2026, 9, 12, 8, 0).isoformat(),
                "values": [{"code": "bp-systolic", "value": 146}, {"code": "bp-diastolic", "value": 92}],
            },
        )
        content = anon.get(f"/my/{token}/content").json()
        assert 'class="trend-chart"' in content["trends"]
        assert content["count"] >= 6
        assert "pp-flag" in content["flags"] or content["flags"] == ""

        # 7) downloads (graphs ke saath)
        pdf = anon.get(f"/my/{token}/export?fmt=pdf")
        assert pdf.status_code == 200 and pdf.content[:5] == b"%PDF-"
        html = anon.get(f"/my/{token}/export?fmt=html")
        assert html.status_code == 200 and 'class="trend-chart"' in html.text
        csv_resp = anon.get(f"/my/{token}/export?fmt=csv")
        assert csv_resp.status_code == 200 and "Date & time" in csv_resp.text

        # 8) portal page par trends + charts render hote hain (server-side)
        page2 = anon.get(f"/my/{token}")
        assert "My trends" in page2.text and 'class="trend-chart"' in page2.text

        # 9) "Doctor ko bhejo" — read-only share link
        share = anon.post(f"/my/{token}/share", json={"note": "BP 3 din se high hai"})
        assert share.status_code == 200, share.text
        share_data = share.json()
        assert share_data["ok"] and "/s/" in share_data["url"]
        share_token = share_data["token"]

    # 10) KOI BHI (bina login, bina cookie) share link khol sakta hai
    with TestClient(main_v2.app) as doctor:
        view = doctor.get(f"/s/{share_token}")
        assert view.status_code == 200
        assert "read-only" in view.text
        assert PNAME in view.text
        assert 'class="trend-chart"' in view.text  # graphs dikhte hain
        assert "Patient ka message" in view.text
        assert "Print / Save as PDF" in view.text
        # read-only: koi write endpoint nahi
        assert doctor.post(f"/s/{share_token}", json={}).status_code == 405
        # share snapshot ka apna download
        spdf = doctor.get(f"/s/{share_token}/export?fmt=pdf")
        assert spdf.status_code == 200 and spdf.content[:5] == b"%PDF-"

    return token, share_token


def test_share_expiry_and_bad_tokens():
    _ensure_patient()
    with _doctor_client() as client:
        link = client.post("/opd/api/patient-link", json={"patient_id": PID}).json()
    token = link["token"]

    with TestClient(main_v2.app) as anon:
        assert anon.get("/my/does-not-exist-token").status_code == 404
        anon.post(f"/my/{token}/verify", json={"phone": PHONE})
        share = anon.post(f"/my/{token}/share", json={}).json()
        share_token = share["token"]

        # expiry: DB me expires_at peeche kar do → page 410 (410 = gone)
        with main_v2.SessionLocal() as session:
            row = session.execute(
                sa.select(PatientShareModel).where(PatientShareModel.token == share_token)
            ).scalar_one()
            row.expires_at = tk.now_utc() - dt.timedelta(days=1)
            session.commit()

        gone = anon.get(f"/s/{share_token}")
        assert gone.status_code == 410
        assert anon.get(f"/s/{share_token}/export?fmt=pdf").status_code == 410
        assert anon.get("/s/unknown-share-token").status_code == 410


def test_doctor_monitor_endpoints():
    _ensure_patient()
    with _doctor_client() as client:
        r = client.get(f"/opd/api/patient-readings?patient_id={PID}")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["ok"] and data["patient_name"] == PNAME
        assert data["count"] >= 1
        assert "trend-chart" in data["trends"]  # doctor ko bhi wahi server-side graph milta hai
        assert "Date &amp; time" in data["table"] or "Date & time" in data["table"]

        # Patient Monitor tab ki list
        listing = client.get("/opd/api/portal-patients").json()
        assert listing["ok"] and listing["count"] >= 1
        row = next(p for p in listing["patients"] if p["patient_id"] == PID)
        assert row["patient_name"] == PNAME
        assert row["count"] >= 1
        assert row["last_label"]
        assert row["last_at_text"]
        assert "last_status" in row and "has_link" in row
        # search filter (naam / ID / phone)
        assert client.get("/opd/api/portal-patients?q=Raj").json()["count"] >= 1
        assert client.get("/opd/api/portal-patients?q=9876543210").json()["count"] >= 1
        assert client.get("/opd/api/portal-patients?q=KoiNahiAisa").json()["count"] == 0

        report = client.get(f"/opd/api/patient-report?patient_id={PID}&fmt=pdf")
        assert report.status_code == 200 and report.content[:5] == b"%PDF-"

        stats = client.get("/opd/api/portal-stats").json()
        assert stats["ok"] and stats["links_total"] >= 1 and stats["readings_total"] >= 1

    # doctor API bina login nahi khulta
    with TestClient(main_v2.app) as anon:
        assert anon.get(f"/opd/api/patient-readings?patient_id={PID}", follow_redirects=False).status_code == 302
        assert anon.get("/opd/api/portal-patients", follow_redirects=False).status_code == 302
        assert anon.post("/opd/api/patient-link", json={"patient_id": PID}, follow_redirects=False).status_code == 302


def test_reading_delete_is_owner_scoped():
    _ensure_patient()
    with _doctor_client() as client:
        token = client.post("/opd/api/patient-link", json={"patient_id": PID}).json()["token"]
    with TestClient(main_v2.app) as anon:
        anon.post(f"/my/{token}/verify", json={"phone": PHONE})
        saved = anon.post(
            f"/my/{token}/readings",
            json={
                "dateTime": dt.datetime(2026, 9, 14, 9, 0).isoformat(),
                "values": [{"code": "weight", "value": 78}],
            },
        ).json()
        assert saved["ok"]
        rid = None
        with main_v2.SessionLocal() as session:
            row = session.execute(
                sa.select(PatientReadingModel)
                .where(PatientReadingModel.patient_id == PID, PatientReadingModel.code == "weight")
                .order_by(PatientReadingModel.created_at.desc())
            ).scalars().first()
            rid = str(row.id)
        assert rid
        assert anon.delete(f"/my/{token}/readings/{rid}").json()["ok"] is True
        # dobara delete → 404 (aur doosre patient ki reading delete nahi ho sakti)
        assert anon.delete(f"/my/{token}/readings/{rid}").status_code == 404
        assert anon.delete(f"/my/{token}/readings/not-my-reading").status_code == 404


# ── public base URL (patient link kabhi toota hua na jaye) ───────────────────
def test_public_base_url_falls_back_when_configured_host_is_dead(monkeypatch):
    """Purana tunnel/Railway URL mar chuka ho to link os se na bane.

    Ye asli bug tha: `.env` me dead `trycloudflare` URL pada tha aur patient ko
    wahi link jata tha → "site not found".
    """
    from src.utils import public_url as pu

    pu.reset_cache()
    monkeypatch.setenv("APP_BASE_URL", "https://rio-minerals-rim-skills.trycloudflare.com")

    import socket as _socket

    def _dead(host, *a, **k):
        raise _socket.gaierror("nodename nor servname provided")

    monkeypatch.setattr(pu.socket, "getaddrinfo", _dead)
    assert pu.host_is_alive("https://rio-minerals-rim-skills.trycloudflare.com") is False

    class _Req:
        base_url = "http://192.168.31.238:8000/"

    assert pu.public_base_url(_Req()) == "http://192.168.31.238:8000"
    status = pu.base_url_status(_Req())
    assert status["configured_alive"] is False
    assert "zinda nahi" in str(status["warning"])
    pu.reset_cache()


def test_public_base_url_uses_configured_when_alive(monkeypatch):
    from src.utils import public_url as pu

    pu.reset_cache()
    monkeypatch.setenv("APP_BASE_URL", "https://gilclinic.duckdns.org")
    monkeypatch.setattr(pu.socket, "getaddrinfo", lambda *a, **k: [("ok",)])

    class _Req:
        base_url = "http://192.168.31.238:8000/"

    assert pu.public_base_url(_Req()) == "https://gilclinic.duckdns.org"
    assert pu.base_url_status(_Req())["warning"] == ""
    pu.reset_cache()


def test_public_base_url_ignores_localhost_setting(monkeypatch):
    from src.utils import public_url as pu

    pu.reset_cache()
    monkeypatch.setenv("APP_BASE_URL", "http://localhost:8000")
    monkeypatch.setattr(pu.socket, "getaddrinfo", lambda *a, **k: [("ok",)])

    class _Req:
        base_url = "https://gilclinic.duckdns.org/"

    assert pu.public_base_url(_Req()) == "https://gilclinic.duckdns.org"
    assert "localhost" in str(pu.base_url_status(_Req())["warning"])
    pu.reset_cache()
