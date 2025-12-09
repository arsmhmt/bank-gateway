from decimal import Decimal

from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):
    dependencies = [
        ("branches", "0004_branch_public_code"),
    ]

    operations = [
        migrations.AddField(
            model_name="branch",
            name="deposit_min_amount",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("10.00"),
                help_text="Public deposit form minimum tutarı. Varsayılan 10₺.",
                max_digits=10,
                validators=[django.core.validators.MinValueValidator(Decimal("0.00"))],
            ),
        ),
        migrations.AddField(
            model_name="branch",
            name="deposit_max_amount",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Site başına maksimum public yatırım tutarı. Boş bırakılırsa limitsiz.",
                max_digits=10,
                null=True,
                validators=[django.core.validators.MinValueValidator(Decimal("0.00"))],
            ),
        ),
        migrations.AddField(
            model_name="branch",
            name="withdraw_min_amount",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("50.00"),
                help_text="Public çekim formu minimum tutarı. Varsayılan 50₺.",
                max_digits=10,
                validators=[django.core.validators.MinValueValidator(Decimal("0.00"))],
            ),
        ),
        migrations.AddField(
            model_name="branch",
            name="withdraw_max_amount",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Site başına maksimum public çekim tutarı. Boş bırakılırsa limitsiz.",
                max_digits=10,
                null=True,
                validators=[django.core.validators.MinValueValidator(Decimal("0.00"))],
            ),
        ),
    ]
