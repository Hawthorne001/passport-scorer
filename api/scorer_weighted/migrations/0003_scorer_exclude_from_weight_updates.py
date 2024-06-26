# Generated by Django 4.2.6 on 2024-01-03 21:46

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scorer_weighted", "0002_alter_binaryweightedscorer_threshold"),
    ]

    operations = [
        migrations.AddField(
            model_name="scorer",
            name="exclude_from_weight_updates",
            field=models.BooleanField(
                default=False,
                help_text="If true, this scorer will be excluded from automatic weight updates and associated rescores",
            ),
        ),
    ]
