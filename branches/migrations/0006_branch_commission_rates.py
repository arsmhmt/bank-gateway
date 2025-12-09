from decimal import Decimal

from django.db import migrations, models
import django.core.validators


def seed_default_commissions(apps, schema_editor):
    Branch = apps.get_model("branches", "Branch")
    for branch in Branch.objects.all():
        branch.deposit_commission_rate = Decimal("4.00")
        branch.withdraw_commission_rate = Decimal("0.00")
        branch.system_commission_rate = Decimal("0.200")
        branch.save(
            update_fields=[
                "deposit_commission_rate",
                "withdraw_commission_rate",
                "system_commission_rate",
            ]
        )


class Migration(migrations.Migration):
    dependencies = [
        ("branches", "0005_branch_amount_limits"),
    ]

    operations = [
        migrations.AddField(
            model_name="branch",
            name="deposit_commission_rate",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                help_text="Siteye uygulanan yatırım komisyon oranı (%).",
                max_digits=5,
                validators=[django.core.validators.MinValueValidator(Decimal("0.00"))],
            ),
        ),
        migrations.AddField(
            model_name="branch",
            name="system_commission_rate",
            field=models.DecimalField(
                decimal_places=3,
                default=Decimal("0.000"),
                help_text="Lider Pay sistem payı (varsayılan 0).",
                max_digits=5,
                validators=[django.core.validators.MinValueValidator(Decimal("0.000"))],
            ),
        ),
        migrations.AddField(
            model_name="branch",
            name="withdraw_commission_rate",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                help_text="Siteye uygulanan çekim komisyon oranı (%).",
                max_digits=5,
                validators=[django.core.validators.MinValueValidator(Decimal("0.00"))],
            ),
        ),
        migrations.RunPython(seed_default_commissions, migrations.RunPython.noop),
    ]
