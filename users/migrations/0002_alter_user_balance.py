# Generated by Django 4.1.4 on 2024-08-30 02:09

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="balance",
            field=models.DecimalField(
                decimal_places=2,
                default=0.0,
                help_text="Amount of 'Beers' currency held by the user",
                max_digits=19,
                validators=[django.core.validators.MinValueValidator(0.0)],
            ),
        ),
    ]
