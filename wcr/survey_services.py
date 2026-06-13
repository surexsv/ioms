"""Survey WCR completion — update enquiry and schedule after survey work."""

from enquiries.models import Enquiry
from scheduling.models import WorkSchedule
from wcr.models import WCR_TYPE_SURVEY, WorkCompletionReport


def complete_survey_wcr(wcr, user=None):
    """Mark survey WCR approved: complete schedule and update enquiry status."""
    if wcr.wcr_type != WCR_TYPE_SURVEY or not wcr.enquiry_id:
        return

    enquiry = wcr.enquiry
    schedule = wcr.schedule or getattr(enquiry, 'field_schedule', None)

    if schedule:
        schedule.status = WorkSchedule.STATUS_COMPLETED
        schedule.save(update_fields=['status', 'updated_at'])

    if enquiry.feasibility_remarks and wcr.feasibility_remarks:
        enquiry.feasibility_remarks = wcr.feasibility_remarks
    elif wcr.feasibility_remarks:
        enquiry.feasibility_remarks = wcr.feasibility_remarks
    if wcr.site_findings:
        enquiry.survey_remarks = (
            enquiry.survey_remarks + '\n\n' + wcr.site_findings
            if enquiry.survey_remarks else wcr.site_findings
        )

    enquiry.status = Enquiry.STATUS_SURVEY_COMPLETED
    enquiry.save(update_fields=['status', 'survey_remarks', 'feasibility_remarks', 'updated_at'])


def survey_wcr_exists_for_schedule(schedule):
    if not schedule.enquiry_id:
        return False
    return WorkCompletionReport.objects.filter(
        enquiry_id=schedule.enquiry_id,
        wcr_type=WCR_TYPE_SURVEY,
    ).exists()
