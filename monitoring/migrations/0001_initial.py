from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Vendor',
            fields=[('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')), ('name', models.CharField(max_length=64, unique=True))],
        ),
        migrations.CreateModel(
            name='DeviceModel',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=64)),
                ('sys_object_id', models.CharField(max_length=64, unique=True)),
                ('max_ports', models.PositiveIntegerField(default=0)),
                ('vendor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='models', to='monitoring.vendor')),
            ],
            options={'unique_together': {('vendor', 'name')}},
        ),
        migrations.CreateModel(
            name='Device',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('hostname', models.CharField(blank=True, max_length=128)),
                ('ip', models.GenericIPAddressField(unique=True)),
                ('community', models.CharField(default='public', max_length=64)),
                ('last_polled', models.DateTimeField(blank=True, null=True)),
                ('status', models.BooleanField(default=False)),
                ('model', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='monitoring.devicemodel')),
            ],
        ),
        migrations.CreateModel(
            name='Interface',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('index', models.PositiveIntegerField()),
                ('name', models.CharField(blank=True, max_length=128)),
                ('admin_status', models.BooleanField(default=False)),
                ('oper_status', models.BooleanField(default=False)),
                ('speed', models.BigIntegerField(blank=True, null=True)),
                ('rx_power', models.FloatField(blank=True, null=True)),
                ('tx_power', models.FloatField(blank=True, null=True)),
                ('vlan', models.CharField(blank=True, max_length=64)),
                ('mac_address', models.CharField(blank=True, max_length=17)),
                ('errors_in', models.PositiveBigIntegerField(blank=True, null=True)),
                ('errors_out', models.PositiveBigIntegerField(blank=True, null=True)),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='interfaces', to='monitoring.device')),
            ],
            options={'unique_together': {('device', 'index')}},
        ),
    ]
