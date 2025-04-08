from django.core.management.base import BaseCommand
from snmp.models import Switch
from snmp.tasks.poll_ports import poll_ports

class Command(BaseCommand):
    help = "Опросить все активные коммутаторы и сохранить порты и статистику."

    def handle(self, *args, **options):
        switches = Switch.objects.filter(status=True).order_by('-pk')
        while True:
            for sw in switches:
                self.stdout.write(f"\n🛰 Опрос {sw.hostname or sw.ip} ({sw.ip})")
                try:
                    poll_ports(sw)
                    self.stdout.write(self.style.SUCCESS(f"✅ Успешно: {sw.ip}"))
                except Exception as e:
                    self.stderr.write(self.style.ERROR(f"❌ Ошибка: {sw.ip} — {e}"))
