# Generated by Django 4.2.6 on 2024-02-20 19:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('snmp', '0002_listmachistory_mac_switchesneighbors_switchesports_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicalswitch',
            name='device_model_local',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AddField(
            model_name='switch',
            name='device_model_local',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
    ]
