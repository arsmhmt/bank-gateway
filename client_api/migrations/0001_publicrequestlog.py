from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("branches", "0005_branch_amount_limits"),
    ]

    operations = [
        migrations.CreateModel(
            name="PublicRequestLog",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "request_type",
                    models.CharField(
                        choices=[("deposit", "Deposit"), ("withdraw", "Withdraw")],
                        max_length=20,
                    ),
                ),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.CharField(blank=True, max_length=512)),
                ("fingerprint", models.CharField(blank=True, max_length=96)),
                ("path", models.CharField(blank=True, max_length=255)),
                ("was_limited", models.BooleanField(default=False)),
                ("limit_scope", models.CharField(blank=True, max_length=32)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "branch",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="public_request_logs",
                        to="branches.branch",
                    ),
                ),
            ],
            options={
                "ordering": ("-created_at",),
            },
        ),
        migrations.AddIndex(
            model_name="publicrequestlog",
            index=models.Index(
                fields=("branch", "request_type", "created_at"),
                name="client_api_publicr_branch__fcad4b_idx",
            ),
        ),
    ]
