# Generated by Django 4.2.6 on 2023-10-10 17:09

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('snmp', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Vendor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('vendor', models.CharField(max_length=200)),
            ],
        ),
        migrations.AddField(
            model_name='olt',
            name='sysinfo',
            field=models.CharField(max_length=300, null=True),
        ),
        migrations.AddField(
            model_name='olt',
            name='uptime',
            field=models.DurationField(null=True),
        ),
        migrations.CreateModel(
            name='Switch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('model', models.CharField(max_length=200)),
                ('ip_addr', models.GenericIPAddressField()),
                ('uptime', models.DurationField(null=True)),
                ('sysinfo', models.CharField(max_length=300, null=True)),
                ('vendor', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='snmp.vendor')),
            ],
        ),
        migrations.AlterField(
            model_name='olt',
            name='vendor',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='snmp.vendor'),
        ),
    ]
