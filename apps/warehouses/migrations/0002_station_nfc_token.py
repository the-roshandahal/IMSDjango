import secrets

import apps.warehouses.models
from django.db import migrations, models


def backfill_nfc_tokens(apps, schema_editor):
    Station = apps.get_model("warehouses", "Station")
    for station in Station.objects.all():
        station.nfc_token = secrets.token_urlsafe(18)
        station.save(update_fields=["nfc_token"])


class Migration(migrations.Migration):

    dependencies = [
        ('warehouses', '0001_initial'),
    ]

    operations = [
        # Added nullable/non-unique first -- a plain AddField with a callable
        # default can apply the SAME literal value to every existing row on
        # some backends (MySQL), which would violate the unique constraint
        # below immediately. Backfill per-row, then tighten the field.
        migrations.AddField(
            model_name='station',
            name='nfc_token',
            field=models.CharField(max_length=32, null=True, editable=False),
        ),
        migrations.RunPython(backfill_nfc_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='station',
            name='nfc_token',
            field=models.CharField(default=apps.warehouses.models._generate_nfc_token, editable=False, max_length=32, unique=True),
        ),
    ]
