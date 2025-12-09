# Generated migration to add payment_token to CryptoPayment
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crypto", "0004_add_fields_crypto_walletconfig"),
    ]

    operations = [
        migrations.AddField(
            model_name='cryptopayment',
            name='payment_token',
            field=models.CharField(max_length=64, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='cryptopayment',
            name='payment_token',
            field=models.CharField(max_length=64, null=True, blank=True, unique=True),
        ),
    ]
