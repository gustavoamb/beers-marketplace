import pytest
import random

from shutil import rmtree
from datetime import datetime, timezone
from decimal import Decimal
from faker import Faker
from uuid import uuid4

from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings

from users.models import User, Profile, Follower, SystemCurrency
from stores.models import Product, Store, StoreHasProduct, Promotion, Purchase
from payments.models import Funding
from administration.models import FundAccount

from common.utils import round_to_fixed_exponent

fake = Faker()
Faker.seed(54321)


@pytest.fixture
def admin_user(db):
    data = {
        "username": "admin_user",
        "email": "admin_user@test.com",
        "type": "PER",
        "stripe_id": "user_stripe_id",
    }
    admin_user = User.objects.create(**data)
    admin_user.is_staff = True
    admin_user.save()
    return admin_user


@pytest.fixture
def user(db):
    data = {
        "username": "natural_person",
        "email": "natural_person@test.com",
        "type": User.Type.PERSON.value,
        "stripe_id": "user_stripe_id",
    }
    user = User.objects.create(**data)
    return user


@pytest.fixture
def user2(db):
    data = {
        "username": "another_natural_person",
        "email": "another_natural_person@test.com",
        "type": User.Type.PERSON.value,
        "stripe_id": "another_user_stripe_id",
    }
    user = User.objects.create(**data)
    return user


@pytest.fixture
def user_with_profile(user):
    data = {
        "name": "Test User - Natural Person",
        "phone": "+584161234567",
        "user": user,
    }
    Profile.objects.create(**data)

    return user


@pytest.fixture(params=[1, 4, 10])
def followers(request, user_with_profile):
    users_data = [
        User(
            username=fake.user_name(),
            email=fake.email(),
            type=User.Type.PERSON.value,
            stripe_id="user_stripe_id",
        )
        for i in range(request.param)
    ]
    users_following = User.objects.bulk_create(users_data)
    data = [
        Follower(user=user_with_profile, follower=follower)
        for follower in users_following
    ]
    followers = Follower.objects.bulk_create(data)

    return followers


@pytest.fixture(params=[2, 5, 12])
def following(request, user_with_profile):
    users_data = [
        User(
            username=fake.user_name(),
            email=fake.email(),
            type=User.Type.PERSON.value,
            stripe_id="user_stripe_id",
        )
        for i in range(request.param)
    ]
    users_followed = User.objects.bulk_create(users_data)
    data = [
        Follower(user=followed, follower=user_with_profile)
        for followed in users_followed
    ]
    following = Follower.objects.bulk_create(data)

    return following


@pytest.fixture
def store_user(db):
    data = {
        "username": "fake_store",
        "email": "fake_store@test.com",
        "type": "STR",
        "stripe_id": "user_stripe_id",
    }
    user = User.objects.create(**data)
    return user


@pytest.fixture
def store(db, store_user):
    data = {
        "user": store_user,
        "name": "My store name",
        "description": "My store's description",
    }
    store = Store.objects.create(**data)
    return store


@pytest.fixture
def make_user():
    def __make_user(data=None):
        if data is None:
            data = {
                "username": fake.user_name(),
                "email": fake.email(),
                "type": User.Type.PERSON.value,
                "stripe_id": uuid4(),
            }

        return User.objects.create(**data)

    return __make_user


@pytest.fixture
def make_store(user):
    def __make_store(data=None):
        if data is None:
            data = {
                "user": user,
                "name": fake.company(),
                "description": fake.catch_phrase(),
            }

        return Store.objects.create(**data)

    return __make_store


@pytest.fixture
def make_product():
    def __make_product(data=None):
        boilerplate_data = {"name": "Test Product"}
        if data is not None:
            boilerplate_data.update(**data)

        data = boilerplate_data
        return Product.objects.create(**data)

    return __make_product


@pytest.fixture
def relate_product_to_store():
    def __relate(product, store):
        return StoreHasProduct.objects.create(
            store=store,
            product=product,
            price=Decimal(str(round_to_fixed_exponent(random.uniform(1, 100)))),
        )

    return __relate


@pytest.fixture()
def products(db):
    data = [
        Product(name="Test Product 1"),
        Product(name="Test Product 2"),
        Product(name="Test Product 3"),
    ]
    products = Product.objects.bulk_create(data)
    return products


@pytest.fixture()
def products_in_store(store, products):
    data = [
        StoreHasProduct(store=store, product=products[0], price=10.25),
        StoreHasProduct(store=store, product=products[1], price=5.00),
        StoreHasProduct(store=store, product=products[2], price=2.00),
    ]
    products_in_store = StoreHasProduct.objects.bulk_create(data)
    return products_in_store


@pytest.fixture()
def make_promotion(store):
    def __make_promotion(data=None):
        if data is None:
            data = {
                "store": store,
                "title": "Promotion Title",
                "description": "promo description",
                "price": Decimal(str(round_to_fixed_exponent(random.uniform(1, 100)))),
            }

        return Promotion.objects.create(**data)

    return __make_promotion


@pytest.fixture()
def promotions(db, store, products):
    data = [
        Promotion(
            id=1,
            store=store,
            title="Test Promotion 1",
            description="Test promotion 1 description",
            price=99.99,
        ),
        Promotion(
            id=2,
            store=store,
            title="Test Promotion 2",
            description="Test promotion 2 description",
            price=15.55,
        ),
    ]
    promotions = Promotion.objects.bulk_create(data)
    return promotions


@pytest.fixture
def purchase(user, user2, store):
    data = {
        "user": user,
        "status": Purchase.Status.PENDING,
        "amount": Decimal("15.50"),
        "reference": "dummy_reference",
        "gift_recipient": user2,
        "store": store,
        "gift_expiration_date": datetime(2022, 1, 1, tzinfo=timezone.utc),
    }
    purchase = Purchase.objects.create(**data)
    return purchase


@pytest.fixture
def delivered_purchase(store, user, user2, products):
    data = {
        "user": user,
        "status": Purchase.Status.DELIVERED,
        "amount": Decimal("50.25"),
        "reference": "dummy_reference",
        "gift_recipient": user2,
        "store": store,
        "gift_expiration_date": datetime(2022, 1, 1, tzinfo=timezone.utc),
    }
    purchase = Purchase.objects.create(**data)
    return purchase


@pytest.fixture
def make_purchase(user, user2, store):
    def __make_purchase(data=None):
        boilerplate_data = {
            "user": user,
            "status": Purchase.Status.PENDING,
            "amount": Decimal("15.50"),
            "reference": "dummy_reference",
            "gift_recipient": user2,
            "store": store,
            "gift_expiration_date": datetime(2022, 1, 1, tzinfo=timezone.utc),
        }
        if data is not None:
            boilerplate_data.update(**data)

        data = boilerplate_data
        return Purchase.objects.create(**data)

    return __make_purchase


@pytest.fixture
def purchases(purchase, delivered_purchase):
    purchases = [purchase, delivered_purchase]
    return purchases


@pytest.fixture
def purchases_v2(user, user2, store):
    data = [
        Purchase(
            user=user,
            status=Purchase.Status.PENDING,
            amount=Decimal(str(round_to_fixed_exponent(random.uniform(1, 100)))),
            reference=f"dummy_reference_${i}",
            gift_recipient=user2,
            store=store,
            gift_expiration_date=datetime(2022, 1, 1, tzinfo=timezone.utc),
        )
        for i in range(10)
    ]
    purchases = Purchase.objects.bulk_create(data)
    return purchases


@pytest.fixture
def fund_account():
    data = {"name": "Test Funds Account", "currency": "USD", "balance": 20.00}
    fund_account = FundAccount.objects.create(**data)
    return fund_account


@pytest.fixture
def fund_accounts():
    data = [
        FundAccount(name="Origin Test Account ", currency="USD", balance=15.00),
        FundAccount(name="Destination Tes  Account ", currency="USD", balance=40.00),
    ]
    accounts = FundAccount.objects.bulk_create(data)
    return accounts


@pytest.fixture
def make_fund_account():
    def __make_fund_account(data=None):
        if data is None:
            data = {"name": "Test Funds Account", "currency": "USD", "balance": 00.00}

        return FundAccount.objects.create(**data)

    return __make_fund_account


@pytest.fixture
def funding(user):
    data = {
        "user": user,
        "amount": 50.0,
        "purchased_via": Funding.PaymentPlatform.STRIPE,
        "status": Funding.Status.SUCCESSFUL,
        "reference": uuid4(),
        "fee": 0,
    }
    funding = Funding.objects.create(**data)
    return funding


@pytest.fixture
def make_funding(user):
    def __make_funding(data=None):
        boilerplate_data = {
            "user": user,
            "amount": 50.0,
            "purchased_via": Funding.PaymentPlatform.STRIPE,
            "status": Funding.Status.SUCCESSFUL,
            "reference": uuid4(),
            "fee": 0,
        }
        if data is not None:
            boilerplate_data.update(**data)

        data = boilerplate_data
        return Funding.objects.create(**data)

    return __make_funding


@pytest.fixture
def system_usd():
    data = {"name": "USD", "iso_code": "USD", "ves_exchange_rate": 10.0}
    system_usd = SystemCurrency.objects.create(**data)
    return system_usd


@pytest.fixture
def test_image():
    png = SimpleUploadedFile("tiny.png", b"valid_png_bin")
    yield png
    rmtree(settings.MEDIA_ROOT, ignore_errors=True)
