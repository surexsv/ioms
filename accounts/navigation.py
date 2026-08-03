"""Role-aware navigation helpers — never redirect to unauthorized pages."""

from accounts.roles import (
    FIELD_ROLES,
    ROLE_DIRECTOR,
    ROLE_OPERATIONS,
    ROLE_PROJECT_MANAGER,
    ROLE_SUPERVISOR,
    user_role,
    is_field_staff,
)


def _dashboard_for_role(user):
    from accounts.permissions import allowed_dashboard_url_name
    return allowed_dashboard_url_name(user)


def schedule_back_navigation(user, schedule):
    """
    Return dict: url_name, pk (optional), label.
    Field team never routed to enquiry/order management pages they cannot access.
    """
    role = user_role(user)
    dashboard = _dashboard_for_role(user)

    if schedule and schedule.order_id:
        if user.is_superuser or role in (ROLE_DIRECTOR, ROLE_OPERATIONS, ROLE_PROJECT_MANAGER, ROLE_SUPERVISOR):
            return {
                'url_name': 'order_detail',
                'pk': schedule.order_id,
                'label': 'Back to Order',
            }
        if is_field_staff(role):
            return {'url_name': dashboard, 'pk': None, 'label': 'Back to My Tasks'}
        return {'url_name': 'schedule_list', 'pk': None, 'label': 'Back to Schedules'}

    if schedule and schedule.enquiry_id:
        return {
            'url_name': 'schedule_edit',
            'pk': schedule.pk,
            'label': 'Back to Schedule',
        }

    return {'url_name': 'schedule_list', 'pk': None, 'label': 'Back to Schedules'}


def wcr_back_navigation(user, schedule=None, enquiry=None):
    """Back link for survey WCR and related field workflows."""
    if schedule:
        return schedule_back_navigation(user, schedule)
    role = user_role(user)
    dashboard = _dashboard_for_role(user)
    if enquiry:
        return {'url_name': 'order_list', 'pk': None, 'label': 'Back to Orders'}
    if is_field_staff(role):
        return {'url_name': dashboard, 'pk': None, 'label': 'Back to My Tasks'}
    if role == ROLE_PROJECT_MANAGER:
        return {'url_name': 'project_manager_dashboard', 'pk': None, 'label': 'Back to Projects'}
    if role == ROLE_SUPERVISOR:
        return {'url_name': 'supervisor_dashboard', 'pk': None, 'label': 'Back to Team Dashboard'}
    return {'url_name': 'schedule_list', 'pk': None, 'label': 'Back to Schedules'}


def redirect_target_after_schedule(user, schedule):
    """Post-save redirect — same rules as back navigation."""
    nav = schedule_back_navigation(user, schedule)
    if nav.get('pk'):
        return (nav['url_name'], nav['pk'])
    return (nav['url_name'],)
