# Generated by Django 4.2.6 on 2024-02-26 06:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('snmp', '0015_switchmodel_max_ports'),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name='switch',
            name='switches_status_82e56c_idx',
        ),
        migrations.AddIndex(
            model_name='switch',
            index=models.Index(fields=['status', 'hostname', 'ip', 'rx_signal', 'tx_signal'], name='switches_status_8f77cc_idx'),
        ),
    ]