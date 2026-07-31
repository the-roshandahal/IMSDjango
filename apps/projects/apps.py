from django.apps import AppConfig


class ProjectsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.projects'
    label = 'projects'

    def ready(self):
        from apps.accounts.services import register_reassignment_check
        from apps.projects.services import check_active_project_supervision

        register_reassignment_check(check_active_project_supervision)
