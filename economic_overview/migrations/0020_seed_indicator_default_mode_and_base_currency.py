"""Seed ``default_mode``, ``base_currency``, and Government Spending rename from JSON."""

import json
from pathlib import Path

from django.db import migrations


def _load_indicator_seed_rows() -> list[dict]:
    """Load indicator seed rows from ``economic_data.json``."""
    json_path = (
        Path(__file__).resolve().parent.parent / "data_sources" / "economic_data.json"
    )
    with open(json_path, encoding="utf-8") as json_file:
        return json.load(json_file)


def seed_indicator_display_fields(apps, _schema_editor) -> None:
    """Copy default_mode / base_currency / type+name from the JSON seed file."""
    EconomicIndicatorInformationModel = apps.get_model(
        "economic_overview", "EconomicIndicatorInformationModel"
    )
    for seed_row in _load_indicator_seed_rows():
        indicator = EconomicIndicatorInformationModel.objects.filter(
            id=seed_row["id"]
        ).first()
        if indicator is None:
            continue
        indicator.default_mode = seed_row.get("default_mode", "Raw")
        indicator.base_currency = seed_row.get("base_currency", "") or ""
        if seed_row.get("type"):
            indicator.type = seed_row["type"]
        if seed_row.get("name"):
            indicator.name = seed_row["name"]
        indicator.save(update_fields=["default_mode", "base_currency", "type", "name"])


def clear_indicator_display_fields(apps, _schema_editor) -> None:
    """Reset seeded display fields to migration defaults (reverse)."""
    EconomicIndicatorInformationModel = apps.get_model(
        "economic_overview", "EconomicIndicatorInformationModel"
    )
    EconomicIndicatorInformationModel.objects.update(
        default_mode="Raw",
        base_currency="",
    )


class Migration(migrations.Migration):
    """Apply JSON seed values for display-mode / currency fields."""

    dependencies = [
        ("economic_overview", "0019_add_indicator_default_mode_and_base_currency"),
    ]

    operations = [
        migrations.RunPython(
            seed_indicator_display_fields, clear_indicator_display_fields
        ),
    ]
