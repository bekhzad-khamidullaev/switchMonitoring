# Generated by Django 4.2.6 on 2024-03-11 06:21

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('snmp', '0018_ats_remove_branch_subnet_branch_ats'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='ats',
            options={'managed': True},
        ),
        migrations.AlterModelOptions(
            name='branch',
            options={'managed': True},
        ),
        migrations.AlterModelOptions(
            name='switchmodel',
            options={'managed': True},
        ),
        migrations.AlterModelOptions(
            name='vendor',
            options={'managed': True},
        ),
        migrations.AlterUniqueTogether(
            name='ats',
            unique_together={('name', 'subnet')},
        ),
        migrations.AlterUniqueTogether(
            name='branch',
            unique_together={('name', 'ats')},
        ),
        migrations.AlterUniqueTogether(
            name='switchmodel',
            unique_together={('vendor', 'device_model')},
        ),
        migrations.AlterModelTable(
            name='ats',
            table='ats',
        ),
        migrations.AlterModelTable(
            name='branch',
            table='branch',
        ),
        migrations.AlterModelTable(
            name='switchmodel',
            table='switch_model',
        ),
        migrations.AlterModelTable(
            name='vendor',
            table='vendor',
        ),
    ]
