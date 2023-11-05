# Generated by Django 4.2.6 on 2023-11-05 16:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('snmp', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='olt',
            name='device_ip',
            field=models.GenericIPAddressField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='switch',
            name='device_ip',
            field=models.GenericIPAddressField(blank=True, null=True),
        ),
    ]
