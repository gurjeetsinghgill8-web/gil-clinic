"""NotificationPreference value object for the Patient Engine.

Controls how and when a patient wants to receive notifications.
Supports multiple channels independently.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NotificationPreference:
    """Immutable notification preferences per patient.

    Attributes:
        push_enabled: Allow browser push notifications (PWA).
        sms_enabled: Allow SMS alerts.
        whatsapp_enabled: Allow WhatsApp messages.
        email_enabled: Allow email notifications.
        sound_enabled: Play sound on status update (PWA).
        vibration_enabled: Vibrate on status update (PWA).
    """

    push_enabled: bool = True
    sms_enabled: bool = False
    whatsapp_enabled: bool = False
    email_enabled: bool = False
    sound_enabled: bool = True
    vibration_enabled: bool = True

    @classmethod
    def default(cls) -> NotificationPreference:
        """Sensible defaults: push + sound + vibration on, others off."""
        return cls(
            push_enabled=True,
            sms_enabled=False,
            whatsapp_enabled=False,
            email_enabled=False,
            sound_enabled=True,
            vibration_enabled=True,
        )

    @classmethod
    def all_off(cls) -> NotificationPreference:
        """Silent mode — no notifications at all."""
        return cls(
            push_enabled=False,
            sms_enabled=False,
            whatsapp_enabled=False,
            email_enabled=False,
            sound_enabled=False,
            vibration_enabled=False,
        )

    @classmethod
    def all_on(cls) -> NotificationPreference:
        """Opt-in to every available channel."""
        return cls(
            push_enabled=True,
            sms_enabled=True,
            whatsapp_enabled=True,
            email_enabled=True,
            sound_enabled=True,
            vibration_enabled=True,
        )

    def with_push(self, enabled: bool = True) -> NotificationPreference:
        """Return updated preference with push setting changed."""
        return NotificationPreference(
            push_enabled=enabled,
            sms_enabled=self.sms_enabled,
            whatsapp_enabled=self.whatsapp_enabled,
            email_enabled=self.email_enabled,
            sound_enabled=self.sound_enabled,
            vibration_enabled=self.vibration_enabled,
        )

    def with_sound(self, enabled: bool = True) -> NotificationPreference:
        """Return updated preference with sound setting changed."""
        return NotificationPreference(
            push_enabled=self.push_enabled,
            sms_enabled=self.sms_enabled,
            whatsapp_enabled=self.whatsapp_enabled,
            email_enabled=self.email_enabled,
            sound_enabled=enabled,
            vibration_enabled=self.vibration_enabled,
        )

    @property
    def any_enabled(self) -> bool:
        """Check if at least one notification channel is active."""
        return any([
            self.push_enabled,
            self.sms_enabled,
            self.whatsapp_enabled,
            self.email_enabled,
        ])

    def __repr__(self) -> str:
        channels = []
        if self.push_enabled:
            channels.append("push")
        if self.sms_enabled:
            channels.append("sms")
        if self.whatsapp_enabled:
            channels.append("whatsapp")
        if self.email_enabled:
            channels.append("email")
        if not channels:
            return "<NotificationPreference SILENT>"
        return f"<NotificationPreference {', '.join(channels)}>"
