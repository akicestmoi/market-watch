"""Enforce one publication schedule per indicator (OneToOne + dedupe)."""

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Count


def dedupe_publication_schedules(apps, _schema_editor) -> None:
    """Keep one schedule per indicator (prefer a dated row), delete the rest."""
    PublicationScheduleModel = apps.get_model(
        "economic_overview", "PublicationScheduleModel"
    )
    duplicate_indicator_ids = (
        PublicationScheduleModel.objects.values("indicator_id")
        .annotate(schedule_count=Count("id"))
        .filter(schedule_count__gt=1)
        .values_list("indicator_id", flat=True)
    )
    for indicator_id in duplicate_indicator_ids:
        schedules = list(
            PublicationScheduleModel.objects.filter(indicator_id=indicator_id).order_by(
                "id"
            )
        )
        dated_schedules = [
            candidate
            for candidate in schedules
            if candidate.previous_publication_date is not None
            or candidate.current_publication_date is not None
            or candidate.next_publication_date is not None
        ]
        keep = dated_schedules[0] if dated_schedules else schedules[0]
        PublicationScheduleModel.objects.filter(indicator_id=indicator_id).exclude(
            pk=keep.pk
        ).delete()


def noop_reverse_dedupe(_apps, _schema_editor) -> None:
    """Duplicate rows cannot be restored after dedupe."""


class Migration(migrations.Migration):
    """Dedupe leftover schedule rows, then make ``indicator`` OneToOne."""

    dependencies = [
        ("economic_overview", "0021_remap_indicator_default_mode_wire_values"),
    ]

    operations = [
        migrations.RunPython(dedupe_publication_schedules, noop_reverse_dedupe),
        migrations.AlterField(
            model_name="publicationschedulemodel",
            name="indicator",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="publication_schedule",
                to="economic_overview.economicindicatorinformationmodel",
            ),
        ),
    ]
