# Generated by Django 4.2.6 on 2024-02-21 04:59

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('snmp', '0008_alter_switch_id'),
    ]

    operations = [
        migrations.RenameField(
            model_name='historicalswitch',
            old_name='mac',
            new_name='switch_mac',
        ),
        migrations.RenameField(
            model_name='switch',
            old_name='mac',
            new_name='switch_mac',
        ),
        migrations.RemoveField(
            model_name='historicalswitch',
            name='device_model_local',
        ),
        migrations.RemoveField(
            model_name='historicalswitch',
            name='device_optical_info',
        ),
        migrations.RemoveField(
            model_name='historicalswitch',
            name='high_signal_value',
        ),
        migrations.RemoveField(
            model_name='historicalswitch',
            name='part_number_uplink',
        ),
        migrations.RemoveField(
            model_name='historicalswitch',
            name='physical',
        ),
        migrations.RemoveField(
            model_name='historicalswitch',
            name='rx_signal_uplink',
        ),
        migrations.RemoveField(
            model_name='historicalswitch',
            name='sfp_vendor_uplink',
        ),
        migrations.RemoveField(
            model_name='historicalswitch',
            name='tx_signal_uplink',
        ),
        migrations.RemoveField(
            model_name='historicalswitch',
            name='uplink',
        ),
        migrations.RemoveField(
            model_name='historicalswitch',
            name='vendor',
        ),
        migrations.RemoveField(
            model_name='switch',
            name='device_model_local',
        ),
        migrations.RemoveField(
            model_name='switch',
            name='device_optical_info',
        ),
        migrations.RemoveField(
            model_name='switch',
            name='high_signal_value',
        ),
        migrations.RemoveField(
            model_name='switch',
            name='part_number_uplink',
        ),
        migrations.RemoveField(
            model_name='switch',
            name='physical',
        ),
        migrations.RemoveField(
            model_name='switch',
            name='rx_signal_uplink',
        ),
        migrations.RemoveField(
            model_name='switch',
            name='sfp_vendor_uplink',
        ),
        migrations.RemoveField(
            model_name='switch',
            name='tx_signal_uplink',
        ),
        migrations.RemoveField(
            model_name='switch',
            name='uplink',
        ),
        migrations.RemoveField(
            model_name='switch',
            name='vendor',
        ),
        migrations.AddField(
            model_name='historicalswitch',
            name='neighbor',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='snmp.switchesneighbors'),
        ),
        migrations.AddField(
            model_name='historicalswitch',
            name='ports',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='snmp.switchesports'),
        ),
        migrations.AddField(
            model_name='switch',
            name='neighbor',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='snmp.switchesneighbors'),
        ),
        migrations.AddField(
            model_name='switch',
            name='ports',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='switch_ports', to='snmp.switchesports'),
        ),
        migrations.AddField(
            model_name='switchesports',
            name='mac_on_port',
            field=models.ForeignKey(default=0, on_delete=django.db.models.deletion.DO_NOTHING, to='snmp.mac'),
        ),
        migrations.AddField(
            model_name='switchesports',
            name='part_number',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='switchesports',
            name='rx_signal',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='switchesports',
            name='sfp_vendor',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='switchesports',
            name='tx_signal',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='mac',
            name='ip',
            field=models.GenericIPAddressField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='mac',
            name='port',
            field=models.ForeignKey(default=0, on_delete=django.db.models.deletion.DO_NOTHING, to='snmp.switchesports'),
        ),
        migrations.AlterField(
            model_name='mac',
            name='switch',
            field=models.ForeignKey(default=0, on_delete=django.db.models.deletion.DO_NOTHING, to='snmp.switch'),
        ),
        migrations.AlterField(
            model_name='switchesports',
            name='switch',
            field=models.ForeignKey(default=0, on_delete=django.db.models.deletion.DO_NOTHING, related_name='switch_ports_reverse', to='snmp.switch'),
        ),
    ]
