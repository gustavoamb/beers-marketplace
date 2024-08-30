import pytest

from decimal import Decimal

from payments.api.validate_order import PrePurchaseValidator


@pytest.mark.django_db
def test_get_products_prices(user, store, products, promotions, products_in_store):
    products_request_data = [
        {"id": products[0].id, "quantity": 5},
        {"id": products[1].id, "quantity": 2},
        {"id": products[2].id, "quantity": 3},
    ]
    validator = PrePurchaseValidator(user, store, products_request_data, promotions)
    products_quantity_price = validator.get_products_prices()
    expected_data = [
        {
            "product": products_in_store[0].product.id,
            "quantity": 5,
            "product__name": "Test Product 1",
            "price": Decimal(10.25),
        },
        {
            "product": products_in_store[1].product.id,
            "quantity": 2,
            "product__name": "Test Product 2",
            "price": Decimal(5),
        },
        {
            "product": products_in_store[2].product.id,
            "quantity": 3,
            "product__name": "Test Product 3",
            "price": Decimal(2),
        },
    ]
    assert products_quantity_price == expected_data


@pytest.mark.django_db
def test_get_promotions_prices(user, store, products, promotions, products_in_store):
    promotions_request_data = [
        {"id": promotions[0].id, "quantity": 1},
        {"id": promotions[1].id, "quantity": 2},
    ]
    validator = PrePurchaseValidator(user, store, products, promotions_request_data)
    promotions_quantity_price = validator.get_promotions_prices()
    expected_data = [
        {"id": 1, "name": "Test Promotion 1", "quantity": 1, "price": 99.99},
        {"id": 2, "name": "Test Promotion 2", "quantity": 2, "price": 15.55},
    ]
    promotions_quantity_price[0]["price"] = float(promotions_quantity_price[0]["price"])
    promotions_quantity_price[1]["price"] = float(promotions_quantity_price[1]["price"])
    assert promotions_quantity_price == expected_data


@pytest.mark.django_db
def test_get_order_total(user, store, products, promotions, products_in_store):
    products_quantity_price = [
        {"id": products[0].id, "quantity": 5, "price": 10.25},
        {"id": products[1].id, "quantity": 2, "price": 5.00},
        {"id": products[2].id, "quantity": 3, "price": 2.00},
    ]
    promotions = [
        {"id": 1, "quantity": 1, "price": Decimal(99.99)},
        {"id": 2, "quantity": 2, "price": Decimal(15.55)},
    ]
    validator = PrePurchaseValidator(user, store, products_quantity_price, promotions)
    promotions_prices = validator.get_promotions_prices()

    total_amount = validator.get_order_total_amount(
        products_quantity_price, promotions_prices
    )

    assert total_amount == 198.34


@pytest.mark.django_db
def test_validate_user_can_purchase_failure(user, store, products, promotions):
    user.balance = 99.99
    user.save()
    user.refresh_from_db()
    order_amount = 100.00
    validator = PrePurchaseValidator(user, store, products, promotions)
    user_can_purchase = validator.validate_user_can_purchase(order_amount)

    assert user_can_purchase is False


@pytest.mark.django_db
def test_validate_user_can_purchase_success(user, store, products, promotions):
    user.balance = 100.01
    user.save()
    user.refresh_from_db()
    order_amount = 100.00
    validator = PrePurchaseValidator(user, store, products, promotions)
    user_can_purchase = validator.validate_user_can_purchase(order_amount)

    assert user_can_purchase is True
