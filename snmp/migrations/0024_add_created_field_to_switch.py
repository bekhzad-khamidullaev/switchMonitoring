import django.utils.timezone
from django.db import migrations, models

def set_created_default(apps, schema_editor):
    Switch = apps.get_model('snmp', 'Switch')
    for switch in Switch.objects.all():
        switch.created = django.utils.timezone.now()
        switch.save()

class Migration(migrations.Migration):

    dependencies = [
        ('snmp', '0023_historicalswitch_ats_switch_ats'),
    ]


    operations = [
        # Add the field with no default value
        migrations.AddField(
            model_name='switch',
            name='created',
            field=models.DateTimeField(auto_now_add=True),
            preserve_default=False,
        ),
        # Set a default value for existing rows
        migrations.RunPython(set_created_default),
    ]
