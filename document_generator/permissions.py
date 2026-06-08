def can_view_document_generator(user):
    return user.is_authenticated and (
        user.is_superuser or getattr(user, 'role', None) == 'DIRECTOR'
    )


def can_manage_document_generator(user):
    return can_view_document_generator(user)
