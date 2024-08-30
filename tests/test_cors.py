from rest_framework import status
from rest_framework.test import APIClient, APIRequestFactory

request_factory = APIRequestFactory()

request_headers = {
    "HTTP_ORIGIN": "http://somethingelse.com",
}
api_client = APIClient(**request_headers)


def test_cors(user):
    api_client.force_authenticate(user=user)
    response = api_client.get("/beers/users/")

    assert response.status_code == status.HTTP_200_OK
    assert response.headers["Access-Control-Allow-Origin"] == "*"
