from django.db import models

from common.models import TimeStampedModel

PUSH_NOTIFICATION_LABEL = {
    "GIFT_ACCEPTED": "Han aceptado tu regalo",
    "GIFT_RECEIVED": "🍺 Te han enviado un regalo!",
    "GIFT_REJECTED": "Han rechazado tu regalo",
}


# Create your models here.
class Notification(TimeStampedModel):
    class Type(models.TextChoices):
        FOLLOWED = "FOLLOWED", "Followed"
        GIFT_ACCEPTED = "GIFT_ACCEPTED", "Regalo aceptado"
        GIFT_RECEIVED = "GIFT_RECEIVED", "🍺 Te han enviado un regalo!"
        GIFT_REJECTED = "GIFT_REJECTED", "Regalo rechazado"

    receiver = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="notifications",
        help_text="User receiving the notification",
    )
    read = models.BooleanField(
        default=False,
        help_text="Indicates if the User has read or not the notification",
    )
    type = models.CharField(
        max_length=23, choices=Type.choices, default=Type.GIFT_RECEIVED
    )
    follower = models.ForeignKey("users.User", on_delete=models.CASCADE, null=True)
    purchase = models.ForeignKey("stores.Purchase", on_delete=models.CASCADE, null=True)
