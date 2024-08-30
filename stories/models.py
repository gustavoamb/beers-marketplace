from django.db import models

from common.models import TimeStampedModel


# Create your models here.
class Story(TimeStampedModel):
    image = models.ImageField(upload_to="users/stories/")
    user = models.ForeignKey("users.User", on_delete=models.CASCADE)
