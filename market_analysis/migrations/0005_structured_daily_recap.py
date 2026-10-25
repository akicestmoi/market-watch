from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("market_analysis", "0004_drop_aux_models"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="dailyrecapmodel",
            name="analysis_content",
        ),
        migrations.AddField(
            model_name="dailyrecapmodel",
            name="main_summary",
            field=models.TextField(
                default="",
                help_text="High-level worldwide mainline (not detailed).",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="dailyrecapmodel",
            name="us_summary",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="dailyrecapmodel",
            name="eur_summary",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="dailyrecapmodel",
            name="jp_summary",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="dailyrecapmodel",
            name="additional_summary",
            field=models.TextField(
                blank=True,
                default="",
                help_text="Commodities, crypto, notable RoW / non-core-zone items.",
            ),
        ),
    ]
