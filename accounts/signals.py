from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from accounts.enterprise_models import EmployeePermissionGrant
from accounts.enterprise_permissions import invalidate_enterprise_permission_cache


@receiver(post_save, sender=EmployeePermissionGrant)
@receiver(post_delete, sender=EmployeePermissionGrant)
def clear_enterprise_permission_cache(sender, instance, **kwargs):
    if instance.employee_id:
        invalidate_enterprise_permission_cache(instance.employee.user_id)
