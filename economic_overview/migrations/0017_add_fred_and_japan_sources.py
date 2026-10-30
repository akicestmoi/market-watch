"""Add FRED and Japan native economic data source choices."""

from django.db import migrations, models


class Migration(migrations.Migration):
    """Widen indicator ``source`` choices for US FRED and Japan agencies."""

    dependencies = [
        ("economic_overview", "0016_add_eurostat_source"),
    ]

    operations = [
        migrations.AlterField(
            model_name="economicindicatorinformationmodel",
            name="source",
            field=models.CharField(
                choices=[
                    ("INSEE", "INSEE"),
                    ("EUROSTAT", "Eurostat"),
                    ("FRED", "FRED"),
                    ("JP_CABINET_OFFICE", "Japan Cabinet Office"),
                    ("STAT_OF_JP", "Statistics of Japan"),
                    ("MLIT", "MLIT"),
                    ("BOJ", "Bank of Japan"),
                ],
                max_length=255,
            ),
        ),
    ]
