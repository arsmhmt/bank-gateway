from decimal import Decimal

from django.db import migrations


def seed_provider_commissions(apps, schema_editor):
    Provider = apps.get_model("provider_panel", "Provider")
    Provider.objects.all().update(
        deposit_commission=Decimal("3.00"),
        withdraw_commission=Decimal("0.00"),
    )


class Migration(migrations.Migration):
    dependencies = [
        ("provider_panel", "0003_provider_wallet_balance"),
    ]

    operations = [
        migrations.RunPython(seed_provider_commissions, migrations.RunPython.noop),
    ]
