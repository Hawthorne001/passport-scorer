# Generated by Django 4.2.6 on 2024-01-08 22:56

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scorer_weighted", "0003_scorer_exclude_from_weight_updates"),
    ]

    operations = [
        migrations.CreateModel(
            name="RescoreRequest",
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
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("RUNNING", "Running"),
                            ("SUCCESS", "Success"),
                            ("FAILED", "Failed"),
                        ],
                        default="RUNNING",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("num_communities_requested", models.IntegerField(default=0)),
                ("num_communities_processed", models.IntegerField(default=0)),
            ],
        ),
    ]
