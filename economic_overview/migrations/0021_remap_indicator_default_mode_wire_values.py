"""Remap ``default_mode`` wire codes to Raw / Quarter / Annualized Quarter / Annual."""

from django.db import migrations, models

_OLD_TO_NEW_DEFAULT_MODE: dict[str, str] = {
    "ABS": "Raw",
    "QOQ": "Quarter",
    "QOQY": "Annualized Quarter",
    "YOY": "Annual",
}
_NEW_TO_OLD_DEFAULT_MODE: dict[str, str] = {
    new_value: old_value for old_value, new_value in _OLD_TO_NEW_DEFAULT_MODE.items()
}

_DEFAULT_MODE_FIELD = models.CharField(
    choices=[
        ("Raw", "Raw"),
        ("Quarter", "Quarter"),
        ("Annualized Quarter", "Annualized Quarter"),
        ("Annual", "Annual"),
    ],
    default="Raw",
    help_text=(
        "Default Raw / Quarter / Annualized Quarter / Annual mode "
        "(UI labels: Abs / QoQ / QoQy / YoY)."
    ),
    max_length=32,
)


def remap_default_mode_to_new_wire_values(apps, _schema_editor) -> None:
    """Rewrite ABS / QOQ / QOQY / YOY rows to the current wire strings."""
    EconomicIndicatorInformationModel = apps.get_model(
        "economic_overview", "EconomicIndicatorInformationModel"
    )
    for old_value, new_value in _OLD_TO_NEW_DEFAULT_MODE.items():
        EconomicIndicatorInformationModel.objects.filter(
            default_mode=old_value
        ).update(default_mode=new_value)


def remap_default_mode_to_old_wire_values(apps, _schema_editor) -> None:
    """Restore legacy ABS / QOQ / QOQY / YOY wire strings (reverse)."""
    EconomicIndicatorInformationModel = apps.get_model(
        "economic_overview", "EconomicIndicatorInformationModel"
    )
    for new_value, old_value in _NEW_TO_OLD_DEFAULT_MODE.items():
        EconomicIndicatorInformationModel.objects.filter(
            default_mode=new_value
        ).update(default_mode=old_value)


class Migration(migrations.Migration):
    """Widen the column on the DB, remap stored codes, then lock model state."""

    dependencies = [
        ("economic_overview", "0020_seed_indicator_default_mode_and_base_currency"),
    ]

    operations = [
        # Existing DBs still have varchar(8) from the originally applied 0019 even
        # when the migration file was later updated to max_length=32.
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE economic_overview_economicindicatorinformationmodel "
                        "ALTER COLUMN default_mode TYPE varchar(32);"
                    ),
                    reverse_sql=(
                        "ALTER TABLE economic_overview_economicindicatorinformationmodel "
                        "ALTER COLUMN default_mode TYPE varchar(8);"
                    ),
                ),
            ],
            state_operations=[],
        ),
        migrations.RunPython(
            remap_default_mode_to_new_wire_values,
            remap_default_mode_to_old_wire_values,
        ),
        migrations.AlterField(
            model_name="economicindicatorinformationmodel",
            name="default_mode",
            field=_DEFAULT_MODE_FIELD,
        ),
    ]
