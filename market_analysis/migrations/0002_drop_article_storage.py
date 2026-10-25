# Drop article storage; keep only source config + recaps / usage / feedback.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("market_analysis", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="agentrunmodel",
            name="related_article",
        ),
        migrations.RemoveField(
            model_name="feedbackmodel",
            name="article",
        ),
        migrations.DeleteModel(name="ArticleAnalysisModel"),
        migrations.DeleteModel(name="ArticleModel"),
        migrations.RenameField(
            model_name="dailyrecapmodel",
            old_name="source_article_ids",
            new_name="source_urls",
        ),
        migrations.AlterField(
            model_name="agentrunmodel",
            name="kind",
            field=models.CharField(
                choices=[
                    ("COLLECTION", "News collection"),
                    ("ANALYSIS", "Article analysis"),
                    ("RECAP", "Daily recap"),
                    ("CHAT", "Interactive chat"),
                    ("FEEDBACK", "Feedback processing"),
                    ("PIPELINE", "Full analysis pipeline"),
                ],
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="agentrunmodel",
            name="related_recap",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="agent_runs",
                to="market_analysis.dailyrecapmodel",
            ),
        ),
    ]
