from django.db import migrations


def seed_site_gateway_configs(apps, schema_editor):
    Branch = apps.get_model("branches", "Branch")
    SiteGatewayConfig = apps.get_model("branches", "SiteGatewayConfig")

    for branch in Branch.objects.all():
        SiteGatewayConfig.objects.get_or_create(
            branch=branch,
            gateway="BANK",
            defaults={"is_enabled": True},
        )


def unseed_site_gateway_configs(apps, schema_editor):
    # No-op: we do not want to delete existing configs on reverse migrations.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("branches", "0007_sitegatewayconfig"),
    ]

    operations = [
        migrations.RunPython(seed_site_gateway_configs, unseed_site_gateway_configs),
    ]
