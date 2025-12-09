from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("provider_panel", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="provider",
            name="limitor",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Teminci için maksimum toplam yatırım tutarı (0 veya boş = limitsiz)",
                max_digits=14,
                null=True,
            ),
        ),
    ]
