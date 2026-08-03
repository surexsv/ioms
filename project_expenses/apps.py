from django.apps import AppConfig


class ProjectExpensesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'project_expenses'
    verbose_name = 'Project Expenses (PEAMS)'

    def ready(self):
        from . import signals  # noqa: F401
