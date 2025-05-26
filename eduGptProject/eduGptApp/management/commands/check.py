from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Checks if management commands are working.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Management command is working fine!'))
