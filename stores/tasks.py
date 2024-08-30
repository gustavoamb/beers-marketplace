from beers.celery import app

from datetime import datetime
from pytz import timezone

from stores.models import Purchase
from stores.serializers import PurchaseSerializer


@app.task(bind=True)
def expire_purchases(self):
    today = datetime.now(tz=timezone("America/Caracas"))
    purchases = Purchase.objects.filter(
        status=Purchase.Status.PENDING.value, gift_expiration_date__lte=today
    )

    purchases_updated = []
    for purchase in purchases:
        data = {"status": Purchase.Status.REJECTED.value}
        purchase_serializer = PurchaseSerializer(
            purchase, data=data, partial=True, context={"expire": True}
        )
        purchase_serializer.is_valid(raise_exception=True)
        purchases_updated.append(purchase_serializer.save())

    return purchases_updated
