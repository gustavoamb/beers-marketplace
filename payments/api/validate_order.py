from decimal import Decimal, ROUND_UP
from django.db.models import F
from stores.models import Promotion, StoreHasProduct


class PrePurchaseValidator:
    def __init__(self, user, store, products, promotions):
        self.user = user
        self.store = store
        self.products = products
        self.promotions = promotions

    def validate_user_can_purchase(self, order_amount):
        return self.user.balance >= order_amount

    def get_products_prices(self):
        if not self.products:
            return []

        sorted_products = sorted(self.products, key=lambda product: Decimal(product["id"]))
        products_ids = [product["id"] for product in sorted_products]
        products_in_db = StoreHasProduct.objects.filter(
            store=self.store, product__in=products_ids
        )
        if not products_in_db.exists():
            raise Exception("Could not find prices for any of the products provided")

        products_prices = list(
            products_in_db.values("product", "product__name", "price")
        )
        sorted_prices = sorted(
            products_prices, key=lambda product_price: product_price["product"]
        )
        products_quantity_price = [
            {"quantity": quantity["quantity"], **price}
            for quantity, price in zip(sorted_products, sorted_prices)
        ]

        return products_quantity_price

    def get_promotions_prices(self):
        if not self.promotions:
            return []

        sorted_promotions = sorted(self.promotions, key=lambda product: product["id"])
        promotions_ids = [promotion["id"] for promotion in sorted_promotions]
        promotions_in_db = Promotion.objects.filter(pk__in=promotions_ids)
        if not promotions_in_db.exists():
            raise Exception("Could not find any of the promotions provided")

        promotions_prices = list(
            promotions_in_db.annotate(name=F("title")).values("id", "name", "price")
        )
        sorted_prices = sorted(
            promotions_prices, key=lambda promotion_price: promotion_price["id"]
        )
        promotions_quantity_price = [
            {**quantity, **price}
            for quantity, price in zip(sorted_promotions, sorted_prices)
        ]

        return promotions_quantity_price

    def get_order_total_amount(
        self, products_quantity_price, promotions_quantity_price
    ):
        products_total = 0
        if products_quantity_price:
            products_total = Decimal(
                sum(
                    [
                        product["quantity"] * product["price"]
                        for product in products_quantity_price
                    ]
                )
            )
            products_total = float(
                products_total.quantize(Decimal("0.01"), rounding=ROUND_UP)
            )

        promotions_total = 0
        if promotions_quantity_price:
            promotions_total = Decimal(
                sum(
                    [
                        promotion["quantity"] * promotion["price"]
                        for promotion in promotions_quantity_price
                    ]
                )
            )
            promotions_total = float(
                promotions_total.quantize(Decimal("0.01"), rounding=ROUND_UP)
            )

        total_amount = products_total + promotions_total
        return total_amount

    def validate_order(self):
        if not self.products and not self.promotions:
            raise Exception(
                "A purchase must contain at least one (1) promotion or product"
            )

        products_quantity_and_price = self.get_products_prices()
        promotions_price = self.get_promotions_prices()
        order_total = self.get_order_total_amount(
            products_quantity_and_price, promotions_price
        )
        user_can_purchase = self.validate_user_can_purchase(order_total)

        response = {
            "products": products_quantity_and_price,
            "promotions": promotions_price,
            "total_amount": order_total,
            "user_can_purchase": user_can_purchase,
        }
        if not user_can_purchase:
            response["message"] = "Insuficient customer balance"

        return response
