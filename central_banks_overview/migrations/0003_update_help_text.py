"""Align central-bank / STIR field help_text with current models.py wording."""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """Update help_text only; no schema shape changes."""

    dependencies = [
        (
            "central_banks_overview",
            "0002_meeting_status_drop_order",
        ),
    ]

    operations = [
        migrations.AlterField(
            model_name="centralbankmeetingmodel",
            name="date",
            field=models.DateTimeField(
                help_text=(
                    "Scheduled announcement time in UTC "
                    "(local announcement time converted on ingest)."
                ),
            ),
        ),
        migrations.AlterField(
            model_name="centralbankmeetingmodel",
            name="status",
            field=models.CharField(
                choices=[
                    ("UPCOMING", "Upcoming"),
                    ("OCCURRED", "Occurred"),
                    ("RATES_INGESTED", "Rates ingested"),
                ],
                default="UPCOMING",
                help_text=(
                    "UPCOMING: scheduled time not yet reached. "
                    "OCCURRED: announcement time past, key rates not ingested yet. "
                    "RATES_INGESTED: decision-day key rates ingested for the display date."
                ),
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="centralbankdatamodel",
            name="central_bank",
            field=models.CharField(
                choices=[
                    ("FRB", "Federal Reserve (FRB)"),
                    ("BOJ", "Bank of Japan (BOJ)"),
                    ("ECB", "European Central Bank (ECB)"),
                ],
                help_text="Central bank to which this data set belongs.",
                max_length=255,
            ),
        ),
        migrations.AlterField(
            model_name="centralbankdatamodel",
            name="date",
            field=models.DateField(
                help_text="Key-rate date (display calendar day, not a datetime)."
            ),
        ),
        migrations.AlterField(
            model_name="centralbankdatamodel",
            name="value",
            field=models.FloatField(
                blank=True,
                default=None,
                help_text="Key-rate level; null when the scrape found none.",
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="stirfuturesmodel",
            name="central_bank",
            field=models.CharField(
                choices=[
                    ("FRB", "Federal Reserve (FRB)"),
                    ("BOJ", "Bank of Japan (BOJ)"),
                    ("ECB", "European Central Bank (ECB)"),
                ],
                help_text="Central bank to which this contract belongs.",
                max_length=255,
            ),
        ),
        migrations.AlterField(
            model_name="stirfuturesmodel",
            name="date",
            field=models.DateField(help_text="Price date."),
        ),
        migrations.AlterField(
            model_name="stirfuturesmodel",
            name="first_accrual_date",
            field=models.DateField(
                blank=True,
                default=None,
                help_text="First accrual date when the source provides one.",
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="stirfuturesmodel",
            name="last_accrual_date",
            field=models.DateField(
                blank=True,
                default=None,
                help_text="Last accrual date when the source provides one.",
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="stirfuturesmodel",
            name="source",
            field=models.CharField(
                choices=[("YAHOO", "Yahoo Finance"), ("TFX", "TFX"), ("PDF", "PDF")],
                help_text="Upstream price source.",
                max_length=255,
            ),
        ),
        migrations.AlterField(
            model_name="stirfuturespriceupdatelogmodel",
            name="stir_futures",
            field=models.ForeignKey(
                help_text="STIR futures this price-update log belongs to.",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="stir_futures_price_update_logs",
                to="central_banks_overview.stirfuturesmodel",
            ),
        ),
    ]
