from django.apps import AppConfig


class ActivityLogsConfig(AppConfig):
    name = 'activity_logs'

    def ready(self):
        from . import signals
