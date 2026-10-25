# Generated manually for INCOME category

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("economic_overview", "0009_alter_economicindicatorinformationmodel_frequency_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="economicindicatorinformationmodel",
            name="category",
            field=models.CharField(
                choices=[
                    ("GROWTH", "Growth"),
                    ("INFLATION", "Inflation"),
                    ("GOVERNMENT", "Government"),
                    ("PRODUCTION", "Production"),
                    ("SALES", "Sales"),
                    ("INCOME", "Income"),
                    ("LABOUR", "Labour"),
                    ("HOUSING", "Housing"),
                    ("CONFIDENCE", "Confidence"),
                ],
                max_length=255,
            ),
        ),
    ]
