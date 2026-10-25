# Generated manually to drop INCOME category

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("economic_overview", "0010_add_income_category"),
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
                    ("LABOUR", "Labour"),
                    ("HOUSING", "Housing"),
                    ("CONFIDENCE", "Confidence"),
                ],
                max_length=255,
            ),
        ),
    ]
