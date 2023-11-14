# Generated by Django 4.2.6 on 2023-11-13 17:34

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import simple_history.models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('snmp', '0006_remove_switch_device_optical_info_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='olt',
            old_name='sysDescr_oid',
            new_name='sysdescr_oid',
        ),
        migrations.RenameField(
            model_name='olt',
            old_name='device_optical_info',
            new_name='uplink',
        ),
        migrations.AddField(
            model_name='olt',
            name='ats',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AddField(
            model_name='olt',
            name='high_signal_value',
            field=models.FloatField(default='11'),
        ),
        migrations.AddField(
            model_name='olt',
            name='part_number',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AddField(
            model_name='olt',
            name='rx_signal',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='olt',
            name='sfp_vendor',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AddField(
            model_name='olt',
            name='tx_signal',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='olt',
            name='device_ip',
            field=models.GenericIPAddressField(blank=True, null=True, unique=True),
        ),
        migrations.AlterField(
            model_name='olt',
            name='status',
            field=models.BooleanField(blank=True, default=False, null=True),
        ),
        migrations.AlterField(
            model_name='olt',
            name='uptime',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.CreateModel(
            name='HistoricalOlt',
            fields=[
                ('id', models.BigIntegerField(auto_created=True, blank=True, db_index=True, verbose_name='ID')),
                ('device_model_local', models.CharField(blank=True, max_length=200, null=True)),
                ('uptime', models.CharField(blank=True, max_length=200, null=True)),
                ('device_hostname', models.CharField(blank=True, max_length=200, null=True)),
                ('device_ip', models.GenericIPAddressField(blank=True, db_index=True, null=True)),
                ('device_snmp_community', models.CharField(default='snmp2netread', max_length=100)),
                ('sysdescr_oid', models.CharField(default='1.3.6.1.2.1.1.1.0', max_length=200)),
                ('status', models.BooleanField(blank=True, default=False, null=True)),
                ('uplink', models.IntegerField(blank=True, null=True)),
                ('tx_signal', models.FloatField(blank=True, null=True)),
                ('rx_signal', models.FloatField(blank=True, null=True)),
                ('sfp_vendor', models.CharField(blank=True, max_length=200, null=True)),
                ('part_number', models.CharField(blank=True, max_length=200, null=True)),
                ('ats', models.CharField(blank=True, max_length=200, null=True)),
                ('high_signal_value', models.FloatField(default='11')),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField(db_index=True)),
                ('history_change_reason', models.CharField(max_length=100, null=True)),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('history_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'historical olt',
                'verbose_name_plural': 'historical olts',
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': ('history_date', 'history_id'),
            },
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
    ]