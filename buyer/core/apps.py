from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        """Импортируем сигналы и задачи при запуске приложения."""
        import core.tasks  # noqa: F401

