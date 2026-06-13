"""RBAC resolution — database permissions with static fallback."""

from django.core.cache import cache

from accounts.roles import normalize_role, user_role

_CACHE_KEY = 'ioms_rbac_role_perms_v1'
_CACHE_TTL = 300


def _static_access():
    from accounts.permissions import _ACCESS
    return _ACCESS


def invalidate_rbac_cache():
    cache.delete(_CACHE_KEY)


def _load_db_permissions():
    cached = cache.get(_CACHE_KEY)
    if cached is not None:
        return cached
    try:
        from accounts.rbac_models import RolePermission, SystemRole
        if not SystemRole.objects.exists():
            return None
        mapping = {}
        for role in SystemRole.objects.filter(is_active=True):
            perms = set(
                RolePermission.objects.filter(role=role)
                .select_related('permission')
                .filter(permission__is_active=True)
                .values_list('permission__codename', flat=True)
            )
            mapping[role.codename] = perms
        cache.set(_CACHE_KEY, mapping, _CACHE_TTL)
        return mapping
    except Exception:
        return None


def permissions_for_role(role):
    role = normalize_role(role or '')
    db_map = _load_db_permissions()
    if db_map is not None and role in db_map:
        return db_map[role]
    return _static_access().get(role, set())


def user_has_permission(user, permission_codename):
    if user is None or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if not getattr(user, 'is_profile_approved', True):
        return False
    return permission_codename in permissions_for_role(user_role(user))


def menu_items_for_user(user):
    """Return active MenuItem queryset visible to user."""
    from accounts.rbac_models import MenuItem
    if not user or not user.is_authenticated:
        return MenuItem.objects.none()
    if user.is_superuser:
        return MenuItem.objects.filter(is_active=True).order_by('sort_order')
    perms = permissions_for_role(user_role(user))
    return MenuItem.objects.filter(
        is_active=True,
        permission__codename__in=perms,
    ).order_by('sort_order')
