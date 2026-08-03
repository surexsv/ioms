"""Sync Special Project daily expenses into PEAMS ledger (financial totals only)."""

import logging

from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='special_projects.DailyExpenseLine')
def peams_sync_daily_expense(sender, instance, **kwargs):
    try:
        from django.db import connection
        if 'project_expenses_ledgertransaction' not in connection.introspection.table_names():
            return
        from .services import seed_default_categories, sync_daily_expense_line
        seed_default_categories()
        sync_daily_expense_line(instance)
    except Exception:
        logger.exception('PEAMS sync failed for DailyExpenseLine pk=%s', getattr(instance, 'pk', None))


@receiver(pre_delete, sender='special_projects.DailyExpenseLine')
def peams_void_daily_expense(sender, instance, **kwargs):
    """
    Void ledger before delete. post_delete is too late when FK is SET_NULL —
    Django nulls daily_expense_line_id before post_delete runs.
    """
    try:
        from .models import LedgerTransaction
        LedgerTransaction.objects.filter(
            daily_expense_line_id=instance.pk, is_void=False,
        ).update(is_void=True)
    except Exception:
        logger.exception('PEAMS void failed for DailyExpenseLine pk=%s', getattr(instance, 'pk', None))
