# Generated by Django 3.0.14 on 2024-07-04 11:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('zabbixapp', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='host',
            name='id',
            field=models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='metric',
            name='id',
            field=models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
    ]
