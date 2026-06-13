"""
Architecture-only hooks for ERMS notifications and advanced workflows.
Wire these when email/WhatsApp/multi-level approval is enabled.
"""


class EmailNotificationAdapter:
    """Send request workflow emails."""

    def send(self, user, subject, body, request=None):
        return False


class WhatsAppNotificationAdapter:
    """Send request workflow WhatsApp messages."""

    def send(self, user, message, request=None):
        return False


class MultiLevelApprovalService:
    """Resolve next approver from approval_chain_config on RequestType."""

    def next_approver(self, employee_request):
        return None


class EscalationService:
    """Escalate overdue requests based on SLA configuration."""

    def check_escalations(self):
        return []
