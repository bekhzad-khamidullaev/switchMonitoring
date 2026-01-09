from django.apps import AppConfig
from django.db.models.signals import post_migrate
from django.contrib.auth.models import Group, Permission

class MonitoringConfig(AppConfig):
    name = 'monitoring'

    def ready(self):
        post_migrate.connect(create_default_groups, sender=self)


def create_default_groups(sender, **kwargs):
    roles = ['viewer', 'operator', 'admin']
    for role in roles:
        Group.objects.get_or_create(name=role)
