from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_alter_user_options_alter_user_managers_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="bankaccount",
            name="account_limit",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Bu hesabın alabileceği maksimum toplam yatırım (0 veya boş = limitsiz)",
                max_digits=12,
                null=True,
            ),
        ),
    ]
