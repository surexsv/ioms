from django.apps import AppConfig


class ProductivityConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'productivity'
    verbose_name = 'Employee Productivity'

    def ready(self):
        import productivity.signals  # noqa: F401
