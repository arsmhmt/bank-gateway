import branches.models
from django.db import migrations, models


def populate_public_codes(apps, schema_editor):
    Branch = apps.get_model("branches", "Branch")

    existing_codes = set(
        Branch.objects.exclude(public_code__isnull=True)
        .exclude(public_code__exact="")
        .values_list("public_code", flat=True)
    )

    for branch in Branch.objects.all():
        if branch.public_code:
            continue

        code = branches.models.generate_public_code()
        while code in existing_codes:
            code = branches.models.generate_public_code()

        branch.public_code = code
        branch.save(update_fields=["public_code"])
        existing_codes.add(code)


class Migration(migrations.Migration):
    dependencies = [
        ("branches", "0003_branch_last_notification_ack_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="branch",
            name="public_code",
            field=models.SlugField(
                max_length=32,
                unique=False,
                null=True,
                blank=True,
                help_text="Permanent code for /p/<code>/deposit|withdraw links.",
            ),
        ),
        migrations.RunPython(populate_public_codes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="branch",
            name="public_code",
            field=models.SlugField(
                max_length=32,
                unique=True,
                default=branches.models.generate_public_code,
                help_text="Permanent code for /p/<code>/deposit|withdraw links.",
            ),
        ),
    ]
