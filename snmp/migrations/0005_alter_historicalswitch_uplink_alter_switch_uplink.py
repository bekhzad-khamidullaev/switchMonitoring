# Generated by Django 4.2.6 on 2024-02-20 19:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('snmp', '0004_historicalswitch_device_optical_info_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='historicalswitch',
            name='uplink',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AlterField(
            model_name='switch',
            name='uplink',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
    ]