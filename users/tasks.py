from beers.celery import app

from common.money_exchange.dolar_venezuela import usd_exchange_rate_service


@app.task(bind=True)
def fetch_api_usd_rate(self):
    usd_exchange_rate_service.fetch_and_set_api_rate()
