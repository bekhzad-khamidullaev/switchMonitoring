# Generated by Django 4.2.6 on 2024-02-21 04:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('snmp', '0007_alter_historicalswitch_snmp_community_ro_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='switch',
            name='id',
            field=models.AutoField(primary_key=True, serialize=False),
        ),
    ]
