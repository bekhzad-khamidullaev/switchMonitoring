from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('snmp', '0030_alertrule_alertevent_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='device',
            old_name='switch',
            new_name='managed_device',
        ),
        migrations.RenameField(
            model_name='switchesports',
            old_name='switch',
            new_name='managed_device',
        ),
        migrations.RenameField(
            model_name='mac',
            old_name='switch',
            new_name='managed_device',
        ),
        migrations.AlterUniqueTogether(
            name='switchesports',
            unique_together={('managed_device', 'port')},
        ),
        migrations.AlterUniqueTogether(
            name='mac',
            unique_together={('managed_device', 'mac', 'vlan')},
        ),
    ]
