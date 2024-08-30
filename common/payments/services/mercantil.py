import os
import requests
import hashlib
import base64
from enum import Enum
from Crypto.Cipher import AES


class AES_pkcs5:
    def __init__(
        self, key: str, mode: AES.MODE_ECB = AES.MODE_ECB, block_size: int = 16
    ):
        self.key = self.setKey(key)
        self.mode = mode
        self.block_size = block_size

    def pad(self, byte_array: bytearray):
        """
        pkcs5 padding
        """
        pad_len = self.block_size - len(byte_array) % self.block_size
        return byte_array + (bytes([pad_len]) * pad_len)

    # pkcs5 - unpadding
    def unpad(self, byte_array: bytearray):
        return byte_array[: -ord(byte_array[-1:])]

    def setKey(self, key: str):
        # convert to bytes
        key = key.encode("utf-8")
        # get the sha1 method - for hashing
        sha256 = hashlib.sha256
        # and use digest and take the last 16 bytes
        key = sha256(key).digest()[:16]
        # now zero pad - just incase
        key = key.zfill(16)
        return key

    def encrypt(self, message: str) -> str:
        # convert to bytes
        byte_array = message.encode("UTF-8")
        # pad the message - with pkcs5 style
        padded = self.pad(byte_array)
        # new instance of AES with encoded key
        cipher = AES.new(self.key, AES.MODE_ECB)
        # now encrypt the padded bytes
        encrypted = cipher.encrypt(padded)
        # base64 encode and convert back to string
        return base64.b64encode(encrypted).decode("utf-8")

    def decrypt(self, message: str) -> str:
        # convert the message to bytes
        byte_array = message.encode("utf-8")
        # base64 decode
        message = base64.b64decode(byte_array)
        # AES instance with the - setKey()
        cipher = AES.new(self.key, AES.MODE_ECB)
        # decrypt and decode
        decrypted = cipher.decrypt(message).decode("utf-8")
        # unpad - with pkcs5 style and return
        return self.unpad(decrypted)


class MercantilService:
    def __init__(self):
        self._api_url = os.getenv("MERCANTIL_API_URL")
        self._app_client_id = os.getenv("MERCANTIL_CLIENT_ID")
        self._session = requests.session()
        self._session.headers.update({"X-IBM-Client-Id": self._app_client_id})

    class ErrorCodes(Enum):
        TRANSACTION_NOT_FOUND = "0330"

    class MobilePaymentsReponse:
        def __init__(self, data):
            self._merchant_info = data.get("merchant_identify")
            self.transactions = data.get("transaction_list", [])
            self.errors = data.get("error_list", [])

        def error_code_in_response_body(self, error_code):
            error_codes = [error["error_code"] for error in self.errors]
            return error_code in error_codes

        def error_messages(self):
            return [error["description"] for error in self.errors]

    def list_mobile_payments(self, filters={}):
        cypher = AES_pkcs5(key=os.getenv("MERCANTIL_ENCRYPTION_KEY"))

        if filters["origin_mobile_number"]:
            filters["origin_mobile_number"] = cypher.encrypt(
                filters["origin_mobile_number"]
            )
        else:
            filters["origin_mobile_number"] = cypher.encrypt(
                os.getenv("MERCANTIL_ORIGIN_MOBILE_NUMBER")
            )

        if filters["destination_mobile_number"]:
            filters["destination_mobile_number"] = cypher.encrypt(
                filters["destination_mobile_number"]
            )

        payload = {
            "merchant_identify": {
                "integratorId": 31,
                "merchantId": os.getenv("MERCANTIL_MERCHANT_ID"),
                "terminalId": 1,
            },
            "client_identify": {
                "ipaddress": "10.0.0.1",
                "browser_agent": "",
                "mobile": {"manufacturer": "", "location": {"lat": 0, "lng": 0}},
            },
            "search_by": {"currency": "ves", **filters},
        }
        http_response = self._session.post(
            f"{self._api_url}/mobile-payment/search", json=payload
        )

        response = self.MobilePaymentsReponse(http_response.json())
        return response
