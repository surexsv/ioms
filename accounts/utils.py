from .permissions import allowed_dashboard_url_name


def dashboard_url_name_for_user(user):
    if not user.is_authenticated:
        return 'login'
    return allowed_dashboard_url_name(user)
