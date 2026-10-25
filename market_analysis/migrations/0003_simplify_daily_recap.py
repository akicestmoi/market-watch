from django.db import migrations, models


def dedupe_recaps_keep_latest(apps, schema_editor):
    DailyRecap = apps.get_model("market_analysis", "DailyRecapModel")
    seen = set()
    for row in DailyRecap.objects.order_by("-date_added", "-id").iterator():
        if row.reporting_date in seen:
            row.delete()
        else:
            seen.add(row.reporting_date)


class Migration(migrations.Migration):

    dependencies = [
        ("market_analysis", "0002_drop_article_storage"),
    ]

    operations = [
        migrations.RunPython(dedupe_recaps_keep_latest, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="dailyrecapmodel",
            name="unique_daily_recap_period_config",
        ),
        migrations.RemoveField(model_name="dailyrecapmodel", name="timezone_name"),
        migrations.RemoveField(model_name="dailyrecapmodel", name="window_start"),
        migrations.RemoveField(model_name="dailyrecapmodel", name="window_end"),
        migrations.RemoveField(model_name="dailyrecapmodel", name="structured"),
        migrations.RemoveField(model_name="dailyrecapmodel", name="config_hash"),
        migrations.RemoveField(
            model_name="dailyrecapmodel", name="no_significant_developments"
        ),
        migrations.RenameField(
            model_name="dailyrecapmodel",
            old_name="body_markdown",
            new_name="analysis_content",
        ),
        migrations.AlterField(
            model_name="dailyrecapmodel",
            name="reporting_date",
            field=models.DateField(unique=True),
        ),
    ]
