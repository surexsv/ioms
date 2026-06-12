"""Role normalization and hierarchy helpers for IOMS v1.1."""

# Canonical role keys (stored in User.role after migration)
ROLE_DIRECTOR = 'DIRECTOR'
ROLE_OPERATIONS = 'OPERATIONS'
ROLE_PROJECT_MANAGER = 'PROJECT_MANAGER'
ROLE_SUPERVISOR = 'SUPERVISOR'
ROLE_ACCOUNTS = 'ACCOUNTS'
ROLE_ENGINEER = 'ENGINEER'
ROLE_TECHNICIAN = 'Technician'

LEGACY_SUPERVISOR = 'Supervisor'

FIELD_ROLES = (ROLE_ENGINEER, ROLE_TECHNICIAN)

# Director → Operations → Project Manager → Supervisor → Engineer/Technician
ROLE_HIERARCHY = (
    ROLE_DIRECTOR,
    ROLE_OPERATIONS,
    ROLE_PROJECT_MANAGER,
    ROLE_SUPERVISOR,
    ROLE_ENGINEER,
    ROLE_TECHNICIAN,
)


def normalize_role(role):
    """Map legacy role strings to canonical v1.1 keys."""
    if role == LEGACY_SUPERVISOR:
        return ROLE_SUPERVISOR
    return role


def user_role(user):
    return normalize_role(getattr(user, 'role', None) or '')


def is_field_staff(role):
    return normalize_role(role) in FIELD_ROLES


def role_rank(role):
    role = normalize_role(role)
    try:
        return ROLE_HIERARCHY.index(role)
    except ValueError:
        return 999


def is_management_role(role):
    return normalize_role(role) in {
        ROLE_DIRECTOR, ROLE_OPERATIONS, ROLE_PROJECT_MANAGER, ROLE_SUPERVISOR,
    }
