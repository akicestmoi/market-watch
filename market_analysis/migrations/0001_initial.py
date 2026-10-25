# Generated manually for market_analysis initial schema

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="NewsSourceModel",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("date_added", models.DateTimeField(auto_now_add=True)),
                ("last_modified", models.DateTimeField(auto_now=True)),
                ("source_id", models.CharField(max_length=64, unique=True)),
                ("name", models.CharField(max_length=200)),
                ("base_url", models.URLField(blank=True, default="", max_length=500)),
                (
                    "fetch_method",
                    models.CharField(
                        choices=[
                            ("RSS", "RSS / Atom feed"),
                            ("HTTPX_HTML", "Static HTML via httpx + trafilatura"),
                            ("PLAYWRIGHT", "JavaScript-rendered page via Playwright"),
                            ("API", "Official HTTP API"),
                        ],
                        default="RSS",
                        max_length=32,
                    ),
                ),
                ("scraper_config", models.JSONField(blank=True, default=dict)),
                ("enabled", models.BooleanField(default=True)),
                ("priority", models.PositiveSmallIntegerField(default=100)),
                ("respect_robots", models.BooleanField(default=True)),
            ],
            options={"ordering": ["priority", "source_id"]},
        ),
        migrations.CreateModel(
            name="GuidelineModel",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("date_added", models.DateTimeField(auto_now_add=True)),
                ("last_modified", models.DateTimeField(auto_now=True)),
                ("version", models.PositiveIntegerField(unique=True)),
                ("title", models.CharField(max_length=200)),
                ("content", models.TextField()),
                ("is_active", models.BooleanField(default=False)),
                ("change_summary", models.TextField(blank=True, default="")),
                ("created_by", models.CharField(blank=True, default="system", max_length=100)),
            ],
            options={"ordering": ["-version"]},
        ),
        migrations.CreateModel(
            name="UserPreferenceModel",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("date_added", models.DateTimeField(auto_now_add=True)),
                ("last_modified", models.DateTimeField(auto_now=True)),
                (
                    "scope",
                    models.CharField(
                        choices=[
                            ("USER", "User-specific"),
                            ("APPLICATION", "Application-wide"),
                        ],
                        default="APPLICATION",
                        max_length=32,
                    ),
                ),
                ("user_key", models.CharField(blank=True, default="", max_length=128)),
                ("key", models.CharField(max_length=100)),
                ("value", models.JSONField(default=dict)),
                ("description", models.TextField(blank=True, default="")),
                ("is_active", models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name="DailyRecapModel",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("date_added", models.DateTimeField(auto_now_add=True)),
                ("last_modified", models.DateTimeField(auto_now=True)),
                ("reporting_date", models.DateField()),
                ("timezone_name", models.CharField(default="Europe/Paris", max_length=64)),
                ("window_start", models.DateTimeField()),
                ("window_end", models.DateTimeField()),
                ("title", models.CharField(max_length=300)),
                ("body_markdown", models.TextField()),
                ("structured", models.JSONField(blank=True, default=dict)),
                ("source_article_ids", models.JSONField(blank=True, default=list)),
                ("model_name", models.CharField(max_length=100)),
                ("prompt_version", models.CharField(blank=True, default="", max_length=64)),
                ("guideline_version", models.PositiveIntegerField(blank=True, null=True)),
                ("config_hash", models.CharField(db_index=True, max_length=64)),
                ("no_significant_developments", models.BooleanField(default=False)),
            ],
            options={"ordering": ["-reporting_date", "-date_added"]},
        ),
        migrations.CreateModel(
            name="ChatSessionModel",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("date_added", models.DateTimeField(auto_now_add=True)),
                ("last_modified", models.DateTimeField(auto_now=True)),
                ("session_key", models.CharField(max_length=64, unique=True)),
                ("user_key", models.CharField(blank=True, default="", max_length=128)),
                ("title", models.CharField(blank=True, default="", max_length=200)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["-last_modified"]},
        ),
        migrations.CreateModel(
            name="ArticleModel",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("date_added", models.DateTimeField(auto_now_add=True)),
                ("last_modified", models.DateTimeField(auto_now=True)),
                ("source_key", models.CharField(db_index=True, max_length=64)),
                ("source_name", models.CharField(max_length=200)),
                ("canonical_url", models.URLField(max_length=1000)),
                ("title", models.CharField(max_length=500)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("retrieved_at", models.DateTimeField()),
                ("content", models.TextField(blank=True, default="")),
                ("content_hash", models.CharField(db_index=True, max_length=64)),
                ("companies", models.JSONField(blank=True, default=list)),
                ("tickers", models.JSONField(blank=True, default=list)),
                ("sectors", models.JSONField(blank=True, default=list)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("FETCHED", "Fetched"),
                            ("ANALYZED", "Analyzed"),
                            ("SKIPPED", "Skipped (duplicate / unchanged)"),
                            ("ERROR", "Error"),
                        ],
                        default="FETCHED",
                        max_length=32,
                    ),
                ),
                ("error_detail", models.TextField(blank=True, default="")),
                (
                    "source",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="articles",
                        to="market_analysis.newssourcemodel",
                    ),
                ),
            ],
            options={"ordering": ["-published_at", "-retrieved_at"]},
        ),
        migrations.CreateModel(
            name="ArticleAnalysisModel",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("date_added", models.DateTimeField(auto_now_add=True)),
                ("last_modified", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(max_length=500)),
                ("summary", models.TextField()),
                (
                    "event_type",
                    models.CharField(
                        choices=[
                            ("EARNINGS", "Earnings"),
                            ("GUIDANCE", "Guidance"),
                            ("M_AND_A", "M&A"),
                            ("REGULATION", "Regulation"),
                            ("MACRO", "Macro / Policy"),
                            ("RATES", "Rates / Central Bank"),
                            ("CREDIT", "Credit"),
                            ("MARKETS", "Markets / Trading"),
                            ("CORPORATE", "Corporate / Operations"),
                            ("OTHER", "Other"),
                        ],
                        max_length=32,
                    ),
                ),
                ("companies", models.JSONField(blank=True, default=list)),
                ("tickers", models.JSONField(blank=True, default=list)),
                ("sectors", models.JSONField(blank=True, default=list)),
                ("relevance_score", models.FloatField()),
                ("importance_score", models.FloatField()),
                (
                    "sentiment",
                    models.CharField(
                        choices=[
                            ("POSITIVE", "Positive"),
                            ("NEUTRAL", "Neutral"),
                            ("NEGATIVE", "Negative"),
                            ("MIXED", "Mixed"),
                        ],
                        max_length=16,
                    ),
                ),
                ("key_facts", models.JSONField(blank=True, default=list)),
                ("evidence", models.JSONField(blank=True, default=list)),
                ("uncertainties", models.JSONField(blank=True, default=list)),
                ("source_url", models.URLField(max_length=1000)),
                ("raw_output", models.JSONField(blank=True, default=dict)),
                ("model_name", models.CharField(max_length=100)),
                ("prompt_version", models.CharField(blank=True, default="", max_length=64)),
                ("guideline_version", models.PositiveIntegerField(blank=True, null=True)),
                (
                    "article",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="analysis",
                        to="market_analysis.articlemodel",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="AgentRunModel",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("date_added", models.DateTimeField(auto_now_add=True)),
                ("last_modified", models.DateTimeField(auto_now=True)),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("INGESTION", "Ingestion"),
                            ("ANALYSIS", "Article analysis"),
                            ("RECAP", "Daily recap"),
                            ("CHAT", "Interactive chat"),
                            ("FEEDBACK", "Feedback processing"),
                        ],
                        max_length=32,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("RUNNING", "Running"),
                            ("SUCCESS", "Success"),
                            ("ERROR", "Error"),
                            ("SKIPPED", "Skipped"),
                        ],
                        default="PENDING",
                        max_length=16,
                    ),
                ),
                ("model_name", models.CharField(blank=True, default="", max_length=100)),
                ("prompt_version", models.CharField(blank=True, default="", max_length=64)),
                ("guideline_version", models.PositiveIntegerField(blank=True, null=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("latency_ms", models.PositiveIntegerField(blank=True, null=True)),
                ("error_detail", models.TextField(blank=True, default="")),
                ("metadata", models.JSONField(blank=True, default=dict)),
                (
                    "related_article",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="agent_runs",
                        to="market_analysis.articlemodel",
                    ),
                ),
                (
                    "related_recap",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="agent_runs",
                        to="market_analysis.dailyrecapmodel",
                    ),
                ),
            ],
            options={"ordering": ["-date_added"]},
        ),
        migrations.CreateModel(
            name="LlmUsageModel",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("date_added", models.DateTimeField(auto_now_add=True)),
                ("last_modified", models.DateTimeField(auto_now=True)),
                ("operation", models.CharField(max_length=64)),
                ("model_name", models.CharField(max_length=100)),
                ("input_tokens", models.PositiveIntegerField(default=0)),
                ("output_tokens", models.PositiveIntegerField(default=0)),
                ("cached_input_tokens", models.PositiveIntegerField(default=0)),
                (
                    "estimated_cost_usd",
                    models.DecimalField(decimal_places=6, default=0, max_digits=12),
                ),
                ("latency_ms", models.PositiveIntegerField(blank=True, null=True)),
                ("pricing_snapshot", models.JSONField(blank=True, default=dict)),
                ("success", models.BooleanField(default=True)),
                ("error_detail", models.TextField(blank=True, default="")),
                ("user_key", models.CharField(blank=True, default="", max_length=128)),
                (
                    "agent_run",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="usage_records",
                        to="market_analysis.agentrunmodel",
                    ),
                ),
            ],
            options={"ordering": ["-date_added"]},
        ),
        migrations.CreateModel(
            name="FeedbackModel",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("date_added", models.DateTimeField(auto_now_add=True)),
                ("last_modified", models.DateTimeField(auto_now=True)),
                ("user_key", models.CharField(blank=True, default="", max_length=128)),
                (
                    "category",
                    models.CharField(
                        choices=[
                            ("FACTUAL", "Factual correction"),
                            ("PREFERENCE", "Preference"),
                            ("SOURCE_QUALITY", "Source quality"),
                            ("PROMPT_FAILURE", "Prompt failure"),
                            ("RANKING", "Ranking / inclusion"),
                            ("OTHER", "Other"),
                        ],
                        max_length=32,
                    ),
                ),
                ("original_output", models.TextField(blank=True, default="")),
                ("feedback_text", models.TextField()),
                ("correction", models.TextField(blank=True, default="")),
                ("proposed_guideline_change", models.TextField(blank=True, default="")),
                (
                    "approval_status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending approval"),
                            ("APPROVED", "Approved"),
                            ("REJECTED", "Rejected"),
                            ("AUTO_APPLIED", "Auto-applied"),
                        ],
                        default="PENDING",
                        max_length=16,
                    ),
                ),
                (
                    "resulting_guideline_version",
                    models.PositiveIntegerField(blank=True, null=True),
                ),
                ("processing_status", models.CharField(default="RAW", max_length=32)),
                ("classification", models.JSONField(blank=True, default=dict)),
                (
                    "article",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="feedback",
                        to="market_analysis.articlemodel",
                    ),
                ),
                (
                    "recap",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="feedback",
                        to="market_analysis.dailyrecapmodel",
                    ),
                ),
            ],
            options={"ordering": ["-date_added"]},
        ),
        migrations.CreateModel(
            name="ChatMessageModel",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("date_added", models.DateTimeField(auto_now_add=True)),
                ("last_modified", models.DateTimeField(auto_now=True)),
                ("role", models.CharField(max_length=16)),
                ("content", models.TextField()),
                ("citations", models.JSONField(blank=True, default=list)),
                (
                    "agent_run",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="chat_messages",
                        to="market_analysis.agentrunmodel",
                    ),
                ),
                (
                    "session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="messages",
                        to="market_analysis.chatsessionmodel",
                    ),
                ),
            ],
            options={"ordering": ["date_added"]},
        ),
        migrations.AddConstraint(
            model_name="userpreferencemodel",
            constraint=models.UniqueConstraint(
                fields=("scope", "user_key", "key"),
                name="unique_preference_scope_user_key",
            ),
        ),
        migrations.AddConstraint(
            model_name="dailyrecapmodel",
            constraint=models.UniqueConstraint(
                fields=("reporting_date", "timezone_name", "config_hash"),
                name="unique_daily_recap_period_config",
            ),
        ),
        migrations.AddConstraint(
            model_name="articlemodel",
            constraint=models.UniqueConstraint(
                fields=("canonical_url",), name="unique_article_canonical_url"
            ),
        ),
        migrations.AddConstraint(
            model_name="articlemodel",
            constraint=models.UniqueConstraint(
                fields=("content_hash", "source_key"),
                name="unique_article_content_hash_per_source",
            ),
        ),
        migrations.AddIndex(
            model_name="articlemodel",
            index=models.Index(
                fields=["status", "retrieved_at"], name="research_ag_status_0e2b1a_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="articlemodel",
            index=models.Index(
                fields=["source_key", "published_at"],
                name="research_ag_source__7c2f11_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="llmusagemodel",
            index=models.Index(
                fields=["model_name", "date_added"],
                name="research_ag_model_n_1a2b3c_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="llmusagemodel",
            index=models.Index(
                fields=["operation", "date_added"],
                name="research_ag_operati_4d5e6f_idx",
            ),
        ),
    ]
