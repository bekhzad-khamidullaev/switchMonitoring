# Generated by Django 4.2.6 on 2024-02-24 07:08

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_alter_customuser_username'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='customuser',
            options={'permissions': [('change_custommodel', 'Can change Custom Model')]},
        ),
    ]
