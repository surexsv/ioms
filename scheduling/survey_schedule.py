"""Auto-create survey schedules when a survey engineer is assigned on an enquiry."""

from django.utils import timezone

from enquiries.models import Enquiry
from productivity.activity_logger import log_activity
from productivity.constants import ACT_SCHEDULE_CREATED, ACT_SURVEY_SCHEDULED
from scheduling.constants import CAT_SURVEY, REF_ENQUIRY
from scheduling.models import WorkSchedule


def ensure_survey_schedule(enquiry, created_by=None):
    """
    Create or update a WorkSchedule for survey field work on this enquiry.
    Returns (schedule, created) or (None, False) if no survey engineer.
    """
    if not enquiry.survey_engineer_id:
        return None, False

    survey_date = enquiry.survey_date or timezone.localdate()
    defaults = {
        'schedule_category': CAT_SURVEY,
        'reference_type': REF_ENQUIRY,
        'reference_number': enquiry.enquiry_number,
        'scheduled_start_date': survey_date,
        'scheduled_end_date': survey_date,
        'status': WorkSchedule.STATUS_ASSIGNED,
        'lead_engineer': enquiry.survey_engineer,
        'work_instructions': (
            f'Site survey for enquiry {enquiry.enquiry_number}. '
            f'{enquiry.description[:200]}'
        ),
    }
    if enquiry.assigned_project_manager_id:
        defaults['project_manager'] = enquiry.assigned_project_manager
    if enquiry.assigned_supervisor_id:
        defaults['supervisor'] = enquiry.assigned_supervisor
    if created_by:
        defaults['created_by'] = created_by

    schedule, created = WorkSchedule.objects.get_or_create(
        enquiry=enquiry,
        defaults=defaults,
    )
    if not created:
        schedule.schedule_category = CAT_SURVEY
        schedule.reference_type = REF_ENQUIRY
        schedule.reference_number = enquiry.enquiry_number
        schedule.scheduled_start_date = survey_date
        schedule.scheduled_end_date = survey_date
        schedule.lead_engineer = enquiry.survey_engineer
        schedule.status = WorkSchedule.STATUS_ASSIGNED
        if enquiry.assigned_project_manager_id:
            schedule.project_manager = enquiry.assigned_project_manager
        if enquiry.assigned_supervisor_id:
            schedule.supervisor = enquiry.assigned_supervisor
        schedule.save()

    _sync_team_from_enquiry(schedule, enquiry)

    if enquiry.status not in (
        Enquiry.STATUS_SURVEY_COMPLETED,
        Enquiry.STATUS_CONVERTED,
        Enquiry.STATUS_WON,
        Enquiry.STATUS_LOST,
        Enquiry.STATUS_CLOSED,
    ):
        if enquiry.status != Enquiry.STATUS_SURVEY_SCHEDULED:
            enquiry.status = Enquiry.STATUS_SURVEY_SCHEDULED
            enquiry.save(update_fields=['status', 'updated_at'])

    if created_by:
        log_activity(
            created_by, ACT_SCHEDULE_CREATED,
            related_document=schedule.schedule_number,
            related_model='WorkSchedule',
            related_object_id=schedule.pk,
            remarks=f'Auto survey schedule for {enquiry.enquiry_number}',
        )
        log_activity(
            created_by, ACT_SURVEY_SCHEDULED,
            related_document=enquiry.enquiry_number,
            related_model='Enquiry',
            related_object_id=enquiry.pk,
        )

    return schedule, created


def _sync_team_from_enquiry(schedule, enquiry):
    engineer = enquiry.survey_engineer
    if not engineer:
        return
    schedule.assigned_engineers.add(engineer)
    if engineer.role == 'Technician':
        schedule.technicians.add(engineer)
    else:
        schedule.supporting_engineers.add(engineer)
