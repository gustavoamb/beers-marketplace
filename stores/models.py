import pytz
from datetime import datetime, timezone, time, timedelta
from uuid import uuid4
from shortuuid import ShortUUID

from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator

from phonenumber_field.modelfields import PhoneNumberField

from common.models import TimeStampedModel

shortuuid = ShortUUID(alphabet="0123456789")


def generate_dispatch_code():
    code = shortuuid.uuid()[:5]
    while Store.objects.filter(dispatch_code=code).exists():
        code = shortuuid.uuid()[:5]

    return code


# Create your models here.
class Product(TimeStampedModel):
    name = models.TextField(help_text="The product's name")
    description = models.TextField(help_text="The product's description", null=True)
    photo = models.ImageField(upload_to="products")


class Store(TimeStampedModel):
    class DocType(models.TextChoices):
        RIF = "RIF", "RIF Number"
        CI = "CI", "ID Number"

    name = models.TextField(help_text="The store's name")
    description = models.TextField(help_text="A description of the store")
    doc_type = models.CharField(max_length=3, choices=DocType.choices, null=True)
    doc_number = models.TextField(null=True)
    location = models.ForeignKey(
        "locations.Location", on_delete=models.CASCADE, null=True
    )
    cover_photo_url = models.TextField(help_text="URL for the store's cover photo")
    user = models.OneToOneField(
        "users.User",
        on_delete=models.CASCADE,
        help_text="The store's user information.",
    )
    phone = PhoneNumberField()
    verified = models.BooleanField(
        default=False,
        help_text="Indicates if this store has been verified/approved by staff",
    )
    contact_name = models.TextField(
        help_text="Name of the person attending when contacting the store", null=True
    )
    contact_job = models.TextField(
        help_text="Occupation/position/job of the contact person in the store",
        null=True,
    )
    contact_phone = models.TextField(help_text="Phone of the contact person", null=True)
    commission_percentage = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        default=0.0,
        help_text="Percentage of money Beers takes per sale",
    )
    products = models.ManyToManyField(Product, through="StoreHasProduct")
    dispatch_code = models.CharField(
        max_length=5, null=True, help_text="Code used to verify purchase dispatchs"
    )

    @property
    def schedule_today(self):
        if not self.scheduleday_set.exists():
            return

        current_datetime = datetime.now(tz=pytz.timezone('America/Caracas'))
        current_weekday = current_datetime.weekday()
        return self.scheduleday_set.get(day=current_weekday)

    @property
    def rating(self):
        "The store's reputation score, a number between 0.0 and 5.0"
        reviews: models.QuerySet = self.reviews.all()
        reviews_avg = reviews.aggregate(models.Avg("rating"))
        return reviews_avg["rating__avg"]

    @property
    def reviews_count(self):
        return self.reviews.count()


class StoreHasProduct(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid4)
    store = models.ForeignKey(
        Store, related_name="product_prices", on_delete=models.CASCADE
    )
    product = models.ForeignKey(
        Product, related_name="store_prices", on_delete=models.CASCADE
    )
    price = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        help_text="The product's price",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("store", "product"), name="store_product_unique_together"
            )
        ]


class UserHasFavoriteStore(TimeStampedModel):
    user = models.ForeignKey("users.User", on_delete=models.CASCADE)
    store = models.ForeignKey("Store", on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("user", "store"), name="user_store_unique_together"
            )
        ]


def generate_purchase_reference():
    return uuid4().hex


class Promotion(TimeStampedModel):
    title = models.CharField(max_length=20)
    description = models.CharField(max_length=200)
    price = models.DecimalField(
        max_digits=19,
        decimal_places=2,
    )
    store = models.ForeignKey(
        "Store", on_delete=models.CASCADE, help_text="The store offering the promotion"
    )
    photo = models.ImageField(upload_to="promotions")


def get_gift_expiration_date():
    current_datetime = datetime.now(tz=timezone.utc)
    timedelta_72_hours = timedelta(hours=72)
    expiration_date = current_datetime + timedelta_72_hours
    return expiration_date


class Purchase(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CLAIMED = "CLAIMED", "Claimed"
        ACCEPTED = "ACCEPTED", "Accepted"
        REJECTED = "REJECTED", "Rejected"
        DELIVERED = "DELIVERED", "Delivered"

    status = models.CharField(
        max_length=9, choices=Status.choices, default=Status.PENDING
    )
    amount = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        help_text="The purchase's total amount",
    )
    reference = models.CharField(
        max_length=255,
        help_text="Reference string used to identify the transaction internally",
        default=generate_purchase_reference,
    )
    qr_scanned = models.BooleanField(
        default=False,
        help_text="Indicates if the Purchase's QR code has been scanned, this allows a Purchase to be claimed",
    )
    store = models.ForeignKey(
        "Store",
        null=True,
        on_delete=models.SET_NULL,
        help_text="The store offering the purchased products",
    )
    user = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="purchases",
        help_text="The user who made the purchase",
    )
    products = models.ManyToManyField(
        Product, related_name="products", through="PurchaseHasProduct"
    )
    promotions = models.ManyToManyField(
        Promotion, related_name="purchases", through="PurchaseHasPromotion"
    )
    gift_recipient = models.ForeignKey(
        "users.User",
        on_delete=models.PROTECT,
        related_name="+",
        help_text="The user receiving the gift",
    )
    gift_expiration_date = models.DateTimeField(default=get_gift_expiration_date)
    store_payment = models.ForeignKey(
        "payments.StorePayment",
        related_name="purchases",
        on_delete=models.SET_NULL,
        null=True,
    )
    message = models.TextField(null=True)
    commission_percentage = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        default=0.0,
        help_text="Commission percentage associated with the store at the time of payment",
    )

    @property
    def products_quantity(self):
        quantity = self.purchasehasproduct_set.aggregate(models.Sum("quantity"))[
            "quantity__sum"
        ]
        return quantity

    @property
    def promotions_quantity(self):
        quantity = self.purchasehaspromotion_set.aggregate(models.Sum("quantity"))[
            "quantity__sum"
        ]
        return quantity

    @property
    def gift_has_expired(self):
        if not self.gift_recipient:
            return False

        delivered_status = self.Status.DELIVERED.value
        rejected_status = self.Status.REJECTED.value
        if self.status in [delivered_status, rejected_status]:
            return False

        current_datetime = datetime.now(tz=timezone.utc)
        has_expired = current_datetime > self.gift_expiration_date

        return has_expired

    @property
    def seconds_before_gift_expiration(self):
        if not self.gift_recipient or self.gift_has_expired:
            return 0

        current_datetime = datetime.now(tz=timezone.utc)
        time_left = self.gift_expiration_date - current_datetime
        seconds_before_expiration = time_left.total_seconds()
        if seconds_before_expiration <= 0:
            return 0

        return seconds_before_expiration

    @property
    def information_template(self):
        if self.gift_recipient and self.gift_has_expired:
            return "qr-template/expiredOrder.html"
        elif self.status == self.Status.ACCEPTED:
            return "qr-template/activeOrder.html"
        elif self.status == self.Status.CLAIMED:
            return "qr-template/deliveredOrder.html"

        raise Exception("Cannot find template name, unrecognized purchase status")

    @property
    def commission_amount(self):
        return self.amount * self.commission_percentage

    @property
    def formatted_updated_at(self):
        return self.updated_at.strftime("%Y/%m/%d %I:%M%p")

    @property
    def reference_number(self):
        return str(self.id).zfill(6)


class PurchaseHasProduct(TimeStampedModel):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField(help_text="Number of products purchased")


class PurchaseHasPromotion(TimeStampedModel):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE)
    promotion = models.ForeignKey(Promotion, on_delete=models.CASCADE)
    quantity = models.IntegerField(help_text="Number of promotions purchased")


class StoreReview(TimeStampedModel):
    content = models.TextField(help_text="The review's content")
    rating = models.IntegerField(
        validators=[MinValueValidator(limit_value=0), MaxValueValidator(limit_value=5)],
        help_text="The rating given to the store by the user, is an integer between 0-5",
    )
    store = models.ForeignKey(Store, related_name="reviews", on_delete=models.CASCADE)
    user = models.ForeignKey("users.User", on_delete=models.CASCADE)

    class Meta:
        unique_together = ["store", "user"]


class ScheduleDay(models.Model):
    class WeekDay(models.IntegerChoices):
        MONDAY = 0, "Monday"
        TUESDAY = 1, "Tuesday"
        WEDNESDAY = 2, "Wednesday"
        THURSDAY = 3, "Thursday"
        FRIDAY = 4, "Friday"
        SATURDAY = 5, "Saturday"
        SUNDAY = 6, "Sunday"

    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    day = models.IntegerField(choices=WeekDay.choices, default=WeekDay.MONDAY)
    open_hour = models.TimeField(
        default=time(hour=9), help_text="Store's opening hours"
    )
    close_hour = models.TimeField(
        default=time(hour=11), help_text="Store's closing hours"
    )
    closed = models.BooleanField(
        default=False, help_text="Indicates if the store is closed or not that day"
    )
