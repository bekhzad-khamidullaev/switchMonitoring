# Generated by Django 4.2.6 on 2024-02-21 05:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('snmp', '0010_alter_historicalswitch_id_alter_switch_id_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='historicalswitch',
            name='id',
            field=models.BigIntegerField(auto_created=True, blank=True, db_index=True, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='switch',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
    ]
