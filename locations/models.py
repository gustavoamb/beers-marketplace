from django.db import models

from common.models import TimeStampedModel


# Create your models here.
class Location(TimeStampedModel):
    latitude = models.DecimalField(max_digits=22, decimal_places=16)
    longitude = models.DecimalField(max_digits=22, decimal_places=16)
