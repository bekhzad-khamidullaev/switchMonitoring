# Generated by Django 4.2.6 on 2024-03-11 06:15

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('snmp', '0017_remove_switchesports_poe_admin_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Ats',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(blank=True, max_length=200, null=True)),
                ('subnet', models.GenericIPAddressField(blank=True, null=True, unique=True)),
            ],
        ),
        migrations.RemoveField(
            model_name='branch',
            name='subnet',
        ),
        migrations.AddField(
            model_name='branch',
            name='ats',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='snmp.ats'),
        ),
    ]
