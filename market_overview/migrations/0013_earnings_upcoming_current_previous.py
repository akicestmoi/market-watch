# Generated manually for upcoming / current / previous earnings slot rename.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("market_overview", "0012_rename_earnings_eps_actual_to_eps"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="earningswatchlistmodel",
            name="weight_as_of",
        ),
        migrations.RemoveField(
            model_name="earningswatchlistmodel",
            name="current_report_status",
        ),
        migrations.RemoveField(
            model_name="earningswatchlistmodel",
            name="previous_report_status",
        ),
        migrations.RemoveField(
            model_name="earningswatchlistmodel",
            name="previous_announcement_datetime",
        ),
        migrations.RenameField(
            model_name="earningswatchlistmodel",
            old_name="current_announcement_datetime",
            new_name="upcoming_announcement_datetime",
        ),
        migrations.RenameField(
            model_name="earningswatchlistmodel",
            old_name="current_reporting_period_end",
            new_name="upcoming_reporting_period_end",
        ),
        migrations.RenameField(
            model_name="earningswatchlistmodel",
            old_name="current_eps_expected",
            new_name="upcoming_eps_expected",
        ),
        migrations.RenameField(
            model_name="earningswatchlistmodel",
            old_name="current_revenue_expected",
            new_name="upcoming_revenue_expected",
        ),
        migrations.RenameField(
            model_name="earningswatchlistmodel",
            old_name="previous_reporting_period_end",
            new_name="current_reporting_period_end",
        ),
        migrations.RenameField(
            model_name="earningswatchlistmodel",
            old_name="previous_eps_expected",
            new_name="current_eps_expected",
        ),
        migrations.RenameField(
            model_name="earningswatchlistmodel",
            old_name="previous_revenue_expected",
            new_name="current_revenue_expected",
        ),
        migrations.AddField(
            model_name="earningswatchlistmodel",
            name="previous_reporting_period_end",
            field=models.DateField(
                blank=True,
                help_text=(
                    "Fiscal period end for the print before the latest. "
                    "Empty when unknown."
                ),
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="earningswatchlistmodel",
            name="previous_eps_expected",
            field=models.FloatField(
                blank=True,
                help_text=(
                    "Consensus EPS that was expected for the print before "
                    "the latest. Empty when unknown."
                ),
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="earningswatchlistmodel",
            name="previous_revenue_expected",
            field=models.FloatField(
                blank=True,
                help_text=(
                    "Consensus total revenue that was expected for the print "
                    "before the latest. Empty when unknown."
                ),
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="earningswatchlistmodel",
            name="upcoming_announcement_datetime",
            field=models.DateTimeField(
                blank=True,
                help_text=(
                    "Next scheduled earnings call time in UTC. Empty when unknown."
                ),
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="earningswatchlistmodel",
            name="upcoming_reporting_period_end",
            field=models.DateField(
                blank=True,
                help_text=(
                    "Fiscal period end for the upcoming earnings print. "
                    "Empty when unknown."
                ),
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="earningswatchlistmodel",
            name="upcoming_eps_expected",
            field=models.FloatField(
                blank=True,
                help_text=(
                    "Consensus EPS expected for the upcoming print. "
                    "Empty when unknown."
                ),
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="earningswatchlistmodel",
            name="upcoming_revenue_expected",
            field=models.FloatField(
                blank=True,
                help_text=(
                    "Consensus total revenue expected for the upcoming print. "
                    "Empty when unknown."
                ),
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="earningswatchlistmodel",
            name="current_reporting_period_end",
            field=models.DateField(
                blank=True,
                help_text=(
                    "Fiscal period end for the latest reported print. "
                    "Empty when unknown."
                ),
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="earningswatchlistmodel",
            name="current_eps",
            field=models.FloatField(
                blank=True,
                help_text="Reported EPS for the latest print. Empty when unknown.",
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="earningswatchlistmodel",
            name="current_eps_expected",
            field=models.FloatField(
                blank=True,
                help_text=(
                    "Consensus EPS that was expected for the latest print. "
                    "Empty when unknown."
                ),
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="earningswatchlistmodel",
            name="current_revenue_expected",
            field=models.FloatField(
                blank=True,
                help_text=(
                    "Consensus total revenue that was expected for the latest "
                    "print. Empty when unknown."
                ),
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="earningswatchlistmodel",
            name="current_revenue",
            field=models.FloatField(
                blank=True,
                help_text=(
                    "Reported total revenue for the latest print. Empty when unknown."
                ),
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="earningswatchlistmodel",
            name="current_operating_income",
            field=models.FloatField(
                blank=True,
                help_text=(
                    "Reported operating income for the latest print. "
                    "Empty when unknown."
                ),
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="earningswatchlistmodel",
            name="current_gross_profit",
            field=models.FloatField(
                blank=True,
                help_text=(
                    "Reported gross profit for the latest print. Empty when unknown."
                ),
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="earningswatchlistmodel",
            name="current_ebitda",
            field=models.FloatField(
                blank=True,
                help_text="Reported EBITDA for the latest print. Empty when unknown.",
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="earningswatchlistmodel",
            name="previous_eps",
            field=models.FloatField(
                blank=True,
                help_text=(
                    "Reported EPS for the print before the latest. Empty when unknown."
                ),
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="earningswatchlistmodel",
            name="previous_revenue",
            field=models.FloatField(
                blank=True,
                help_text=(
                    "Reported total revenue for the print before the latest. "
                    "Empty when unknown."
                ),
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="earningswatchlistmodel",
            name="previous_operating_income",
            field=models.FloatField(
                blank=True,
                help_text=(
                    "Reported operating income for the print before the latest. "
                    "Empty when unknown."
                ),
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="earningswatchlistmodel",
            name="previous_gross_profit",
            field=models.FloatField(
                blank=True,
                help_text=(
                    "Reported gross profit for the print before the latest. "
                    "Empty when unknown."
                ),
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="earningswatchlistmodel",
            name="previous_ebitda",
            field=models.FloatField(
                blank=True,
                help_text=(
                    "Reported EBITDA for the print before the latest. "
                    "Empty when unknown."
                ),
                null=True,
            ),
        ),
    ]
