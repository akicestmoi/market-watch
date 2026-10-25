from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("market_analysis", "0003_simplify_daily_recap"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="dailyrecapmodel",
            name="guideline_version",
        ),
        migrations.DeleteModel(name="ChatMessageModel"),
        migrations.DeleteModel(name="ChatSessionModel"),
        migrations.DeleteModel(name="FeedbackModel"),
        migrations.DeleteModel(name="LlmUsageModel"),
        migrations.DeleteModel(name="AgentRunModel"),
        migrations.DeleteModel(name="UserPreferenceModel"),
        migrations.DeleteModel(name="GuidelineModel"),
        migrations.DeleteModel(name="NewsSourceModel"),
    ]
