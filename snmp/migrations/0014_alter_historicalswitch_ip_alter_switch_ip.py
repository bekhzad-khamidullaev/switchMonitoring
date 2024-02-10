# Generated by Django 4.2.6 on 2024-02-10 17:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('snmp', '0013_alter_historicalswitch_high_signal_value_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='historicalswitch',
            name='ip',
            field=models.GenericIPAddressField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='switch',
            name='ip',
            field=models.GenericIPAddressField(blank=True, null=True),
        ),
    ]
