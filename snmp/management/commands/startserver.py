from django.core.management.base import BaseCommand
from django.core.management import call_command
import subprocess

class Command(BaseCommand):
    help = 'Starts the development server indefinitely'

    def handle(self, *args, **options):
        subprocess.run(["python", "manage.py", "runserver", "0.0.0.0:8080"])