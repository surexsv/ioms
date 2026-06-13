"""Unified schedule engine — team queries and reference resolution."""

from django.db.models import Q

from accounts.roles import ROLE_ENGINEER, ROLE_TECHNICIAN, user_role


def schedules_for_user(user):
    """All schedules where user is on the assigned team (including survey enquiries)."""
    from scheduling.models import WorkSchedule

    if not user or not user.is_authenticated:
        return WorkSchedule.objects.none()

    qs = WorkSchedule.objects.exclude(status=WorkSchedule.STATUS_CANCELLED)
    if user.is_superuser or user_role(user) in ('DIRECTOR', 'OPERATIONS', 'PROJECT_MANAGER'):
        return qs.select_related('order', 'order__client', 'enquiry', 'enquiry__client')

    return qs.filter(
        Q(lead_engineer=user)
        | Q(supporting_engineers=user)
        | Q(technicians=user)
        | Q(assigned_engineers=user)
        | Q(team_leader=user)
        | Q(project_manager=user)
        | Q(supervisor=user)
        | Q(enquiry__survey_engineer=user)
    ).select_related(
        'order', 'order__client', 'enquiry', 'enquiry__client',
    ).distinct()


def user_on_schedule_team(schedule, user):
    if not schedule or not user:
        return False
    if schedule.lead_engineer_id == user.pk:
        return True
    if schedule.team_leader_id == user.pk:
        return True
    if schedule.project_manager_id == user.pk:
        return True
    if schedule.supervisor_id == user.pk:
        return True
    if schedule.assigned_engineers.filter(pk=user.pk).exists():
        return True
    if schedule.supporting_engineers.filter(pk=user.pk).exists():
        return True
    if schedule.technicians.filter(pk=user.pk).exists():
        return True
    if schedule.enquiry_id and schedule.enquiry.survey_engineer_id == user.pk:
        return True
    return False


def resolve_reference_display(schedule):
    if schedule.reference_number:
        return schedule.reference_number
    if schedule.enquiry_id:
        return schedule.enquiry.enquiry_number
    if schedule.order_id:
        return schedule.order.order_no or str(schedule.order.order_id)
    return schedule.schedule_number or '—'


def resolve_client_name(schedule):
    if schedule.order_id:
        return schedule.order.client.name
    if schedule.enquiry_id:
        return schedule.enquiry.client.name
    return '—'


def resolve_detail_url(schedule):
    if schedule.order_id:
        return ('order_detail', schedule.order_id)
    if schedule.enquiry_id:
        return ('enquiry_detail', schedule.enquiry_id)
    return None


def category_from_order(order):
    from scheduling.constants import ORDER_TYPE_TO_CATEGORY, CAT_PROJECT
    return ORDER_TYPE_TO_CATEGORY.get(order.order_type, CAT_PROJECT)


def category_from_enquiry(enquiry):
    from scheduling.constants import ENQUIRY_TYPE_TO_CATEGORY, CAT_SURVEY
    if enquiry.survey_required and enquiry.status in (
        'ASSIGNED', 'SURVEY_SCHEDULED', 'NEW',
    ):
        return CAT_SURVEY
    return ENQUIRY_TYPE_TO_CATEGORY.get(enquiry.enquiry_type, CAT_SURVEY)
