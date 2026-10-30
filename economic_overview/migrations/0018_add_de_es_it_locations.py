"""Add Germany, Spain, and Italy to economic indicator location choices."""

from django.db import migrations, models


class Migration(migrations.Migration):
    """Widen indicator ``location`` choices for Eurostat DE / ES / IT series."""

    dependencies = [
        ("economic_overview", "0017_add_fred_and_japan_sources"),
    ]

    operations = [
        migrations.AlterField(
            model_name="economicindicatorinformationmodel",
            name="location",
            field=models.CharField(
                choices=[
                    ("US", "United States"),
                    ("EU", "Europe"),
                    ("DE", "Germany"),
                    ("ES", "Spain"),
                    ("IT", "Italy"),
                    ("FR", "France"),
                    ("JP", "Japan"),
                ],
                max_length=255,
            ),
        ),
    ]
