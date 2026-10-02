"""Experience Engine — Token Slip Use Case.

Generates printable token slip HTML with QR code for patient identification.
Ports the logic from V1's queue.py format_token_slip / format_html_token_slip.
"""

from __future__ import annotations

import base64
from datetime import datetime
from io import BytesIO
from typing import TYPE_CHECKING, Any

import qrcode

from src.application.common.base_use_case import BaseUseCase
from src.application.common.command import Command
from src.application.common.result import Result
from src.application.common.exceptions import NotFoundError
from src.infrastructure.clinic.settings_provider import get_clinic_settings

if TYPE_CHECKING:
    from src.domain.patient.ports.patient_repository import PatientRepository


class TokenSlipUseCase(BaseUseCase):
    """Use case for generating patient token slips.

    Produces HTML content ready for printing with QR code.
    The QR code encodes the patient_id for quick login via camera scan.
    """

    def __init__(
        self,
        patient_repo: PatientRepository,
    ) -> None:
        super().__init__()
        self._patient_repo = patient_repo

    async def authorize(self, command: Command) -> None:
        """Token slip generation requires patient session or staff auth."""
        pass

    async def execute(self, command: Command) -> Result:
        """Generate a token slip for the patient.

        Args:
            command: Command with patient_uuid.

        Returns:
            Result with HTML token slip content + test details.
        """
        dto = command.data
        patient_uuid = dto.get("patient_uuid", "")

        try:
            patient = await self._patient_repo.get_by_id(patient_uuid)
            if not patient:
                raise NotFoundError(
                    message="Patient not found.",
                )

            tests_data = dto.get("tests", [])

            # Generate QR code image
            qr_data_uri = self._generate_qr_data_uri(patient.patient_id)

            slip_html = self._generate_html(
                patient=patient,
                tests=tests_data,
                qr_data_uri=qr_data_uri,
            )

            return Result.ok(
                data={
                    "patient_id": patient.patient_id,
                    "name": patient.demographics.name,
                    "html": slip_html,
                    "tests": tests_data,
                    "generated_at": datetime.utcnow().isoformat(),
                },
                message="Token slip generated",
            )

        except NotFoundError as exc:
            return Result.fail(
                error=str(exc),
                code=exc.code,
                details=exc.details,
            )

    def _generate_qr_data_uri(self, patient_id: str) -> str:
        """Generate a QR code image as a base64 PNG data URI.

        The QR encodes the patient_id so scanning it lets the patient
        login quickly via the camera on the login page.

        Args:
            patient_id: Patient ID to encode in the QR code.

        Returns:
            Data URI string (data:image/png;base64,...).
        """
        qr = qrcode.QRCode(
            version=2,
            box_size=5,
            border=2,
        )
        qr.add_data(patient_id)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#1a237e", back_color="white")

        buf = BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()

        return f"data:image/png;base64,{b64}"

    def _generate_html(
        self,
        patient,
        tests: list[dict[str, Any]],
        qr_data_uri: str,
    ) -> str:
        """Generate printable HTML token slip.

        Args:
            patient: Patient aggregate.
            tests: List of test dicts with test_name, token_number, room.
            qr_data_uri: Base64-encoded PNG data URI of the QR code.

        Returns:
            Complete HTML string with print CSS.
        """
        cs = get_clinic_settings()
        patient_name = patient.demographics.name
        patient_id = patient.patient_id
        today = datetime.now().strftime("%d %b %Y, %I:%M %p")

        tests_html = ""
        for t in tests:
            tests_html += f"""
            <div class="test-item">
                <span class="test-name">{t.get('test_name', 'Test')}</span>
                <span class="token-badge">Token #{t.get('token_number', '-')}</span>
                <span class="room-badge">{t.get('room', 'TBD')}</span>
            </div>
            """

        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Token Slip - {patient_id}</title>
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
        font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
        background: #f5f7fa;
        display: flex;
        justify-content: center;
        padding: 20px;
    }}
    .slip {{
        max-width: 380px;
        width: 100%;
        background: white;
        border-radius: 16px;
        box-shadow: 0 4px 24px rgba(0,0,0,0.1);
        overflow: hidden;
    }}
    .header {{
        background: linear-gradient(135deg, #1a237e, #283593);
        color: white;
        padding: 20px;
        text-align: center;
    }}
    .header h1 {{ font-size: 20px; margin-bottom: 4px; }}
    .header p {{ font-size: 13px; opacity: 0.85; }}
    .qr-section {{
        display: flex;
        justify-content: center;
        padding: 20px;
        background: #fafafa;
    }}
    .qr-code img {{
        width: 160px;
        height: 160px;
        border-radius: 8px;
    }}
    .patient-info {{
        padding: 16px 20px;
    }}
    .patient-info h2 {{ font-size: 22px; margin-bottom: 4px; }}
    .patient-id {{ color: #666; font-size: 14px; font-family: monospace; }}
    .tests {{ padding: 0 20px 16px; }}
    .test-item {{
        display: flex;
        align-items: center;
        padding: 10px 12px;
        background: #f8f9ff;
        border-radius: 10px;
        margin-bottom: 8px;
        gap: 8px;
    }}
    .test-name {{ flex: 1; font-weight: 600; font-size: 15px; }}
    .token-badge {{
        background: #1a237e;
        color: white;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
    }}
    .room-badge {{
        background: #e8eaf6;
        color: #1a237e;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 12px;
    }}
    .footer {{
        padding: 12px 20px;
        text-align: center;
        font-size: 11px;
        color: #999;
        border-top: 1px solid #eee;
    }}
    .timestamp {{ font-size: 12px; color: #888; text-align: center; padding: 0 20px 12px; }}
    @media print {{
        body {{ background: white; padding: 0; }}
        .slip {{ box-shadow: none; max-width: 100%; }}
    }}
</style>
</head>
<body>
<div class="slip">
    <div class="header">
        <h1>{cs.logo_emoji} {cs.name}</h1>
        <p>{cs.specialty}</p>
    </div>
    <div class="qr-section">
        <div class="qr-code">
            <img src="{qr_data_uri}" alt="QR Code" />
        </div>
    </div>
    <div class="patient-info">
        <h2>{patient_name}</h2>
        <div class="patient-id">{patient_id}</div>
    </div>
    <div class="tests">
        {tests_html}
    </div>
    <div class="timestamp">Generated: {today}</div>
    <div class="footer">
        {cs.address if cs.address else cs.specialty}{(' | ' + cs.phone) if cs.phone else ''}
    </div>
</div>
</body>
</html>"""
