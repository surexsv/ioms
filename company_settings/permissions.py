def can_view_company_settings(user):
    return user.is_authenticated and (
        user.is_superuser or getattr(user, 'role', None) == 'DIRECTOR'
    )


def can_manage_company_settings(user):
    return can_view_company_settings(user)


def can_edit_document_signatory(user):
    """Superuser, Director, and Accounts users may set per-document signatory."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return getattr(user, 'role', None) in ('DIRECTOR', 'ACCOUNTS')
