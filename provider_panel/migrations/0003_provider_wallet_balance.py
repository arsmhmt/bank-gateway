from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("provider_panel", "0002_provider_limitor"),
    ]

    operations = [
        migrations.AddField(
            model_name="provider",
            name="wallet_balance",
            field=models.DecimalField(
                max_digits=14,
                decimal_places=2,
                default=0.00,
                help_text="Temincinin cüzdan bakiyesi",
            ),
        ),
    ]
