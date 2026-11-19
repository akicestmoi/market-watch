"""Publication schedules for economic indicator release timing."""

from django.db import models

from core.models import BaseModel
from economic_overview.models.economic_indicators import (
    EconomicIndicatorInformationModel,
)


class PublicationScheduleModel(BaseModel):
    """Release calendar for one indicator (previous, current, and next UTC times)."""

    indicator = models.OneToOneField(
        EconomicIndicatorInformationModel,
        on_delete=models.CASCADE,
        related_name="publication_schedule",
        help_text="Indicator this publication schedule belongs to.",
    )
    previous_publication_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Previous release time in UTC. Empty when we do not know it yet.",
    )
    current_publication_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Latest release time in UTC. Empty when we do not know it yet.",
    )
    next_publication_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Next planned release time in UTC. Empty when we do not know it yet.",
    )
