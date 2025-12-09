from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crypto", "0003_cryptopayment_direction_alter_cryptopayment_address_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="cryptowalletconfig",
            name="label",
            field=models.CharField(
                max_length=64,
                blank=True,
                default="",
                help_text="Opsiyonel açıklama: Örn. Ana Ledger Cüzdanı",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="cryptowalletconfig",
            name="is_deposit_enabled",
            field=models.BooleanField(
                default=True,
                help_text="Yeni yatırımlar için bu adres kullanılabilir mi?",
            ),
        ),
        migrations.AddField(
            model_name="cryptowalletconfig",
            name="min_deposit_amount",
            field=models.DecimalField(
                null=True,
                blank=True,
                max_digits=18,
                decimal_places=8,
                help_text="Opsiyonel minimum yatırım (boş bırakılırsa sınır yok).",
            ),
        ),
        migrations.AddField(
            model_name="cryptowalletconfig",
            name="explorer_url_override",
            field=models.URLField(blank=True, default="", help_text="Opsiyonel özel blockchain explorer bağlantısı."),
            preserve_default=False,
        ),
    ]
