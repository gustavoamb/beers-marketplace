from uuid import uuid4

from django.db import models
from django.contrib.auth.models import AbstractUser, UserManager
from django.core.validators import MinValueValidator

from phonenumber_field.modelfields import PhoneNumberField

from common.models import TimeStampedModel


# Create your models here.
class User(AbstractUser, TimeStampedModel):
    class Type(models.TextChoices):
        PERSON = "PER", "PERSON"
        STORE = "STR", "STORE"

    email = models.EmailField(unique=True)
    type = models.CharField(
        max_length=3,
        choices=Type.choices,
        default=Type.PERSON,
        help_text="The user's type, can be either 'PERSON' or 'STORE'",
    )
    location = models.ForeignKey(
        "locations.Location", on_delete=models.CASCADE, null=True
    )
    balance = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        help_text="Amount of 'Beers' currency held by the user",
        default=0.00,
        validators=[MinValueValidator(0.00)],
    )
    followers = models.ManyToManyField(
        "self",
        through="Follower",
        related_name="followings",
        symmetrical=False,
        help_text="Users following this user",
    )
    stripe_id = models.CharField(max_length=25, help_text="Stripe Customer object ID")
    photo = models.ImageField(upload_to="users", null=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username", "type"]

    @property
    def name(self):
        return f"{self.first_name} {self.last_name}"


class Follower(TimeStampedModel):
    user = models.ForeignKey(
        User,
        related_name="user_followers",
        on_delete=models.CASCADE,
        help_text="The user being followed",
    )
    follower = models.ForeignKey(
        User,
        related_name="user_followings",
        on_delete=models.CASCADE,
        help_text="The user following",
    )
    follower_caught_up_with_stories = models.BooleanField(
        default=False,
        help_text="Indicates if the follower is caught up with the stories of the user they're following",
    )

    class Meta:
        unique_together = ["user", "follower"]


class Profile(models.Model):
    name = models.CharField(max_length=255, help_text="User's full name")
    birthday = models.DateField(
        help_text="The user's birthday date in YYYY-MM-DD format",
        blank=True,
        null=True,
    )
    phone = PhoneNumberField()
    description = models.TextField(
        help_text="The user's description", blank=True, default=""
    )
    cover_photo_url = models.TextField(help_text="URL for the user's cover photo")
    profile_photo_url = models.TextField(help_text="URL for the user's profile photo")
    user = models.OneToOneField("User", on_delete=models.CASCADE)
    updated_at = models.DateTimeField(auto_now=True)


class SystemCurrency(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid4)
    name = models.TextField()
    iso_code = models.CharField(max_length=3, unique=True, help_text="ISO 4217 code")
    ves_exchange_rate = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        help_text="Exchange rate to VES",
    )
