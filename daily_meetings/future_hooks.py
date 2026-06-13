"""
Future integration hooks — architecture only (not implemented).

Planned channels:
- Meeting reminders (push/in-app)
- WhatsApp reminders via provider adapter
- Email MOM distribution
- AI meeting summary from discussions + transcripts

Wire implementations here without changing view/service contracts.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class NotificationPayload:
    meeting_id: int
    meeting_number: str
    meeting_date: str
    recipient_user_ids: list
    channel: str  # 'email' | 'whatsapp' | 'in_app'
    subject: str
    body: str


class MeetingNotificationService:
    """Stub — implement send_reminder(), send_mom(), send_action_due()."""

    def send_reminder(self, meeting_id: int, lead_minutes: int = 30) -> bool:
        raise NotImplementedError('Meeting notifications not enabled')

    def send_mom(self, meeting_id: int, recipient_emails: Optional[list] = None) -> bool:
        raise NotImplementedError('Email MOM distribution not enabled')

    def send_action_due(self, action_id: int) -> bool:
        raise NotImplementedError('Action due notifications not enabled')


class WhatsAppReminderAdapter:
    """Stub — plug Twilio/Meta Business API here."""

    def send(self, phone: str, message: str) -> bool:
        raise NotImplementedError('WhatsApp integration not enabled')


class AIMeetingSummaryService:
    """Stub — summarize discussions + decisions + actions."""

    def summarize(self, meeting_id: int) -> str:
        raise NotImplementedError('AI meeting summary not enabled')


def get_notification_service():
    return MeetingNotificationService()
