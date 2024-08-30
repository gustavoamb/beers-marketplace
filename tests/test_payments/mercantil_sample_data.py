mobile_payments_not_found_response = {
    "processing_date": "2023-11-08 10:51:28 VET",
    "merchant_identify": {
        "integratorId": 31,
        "merchantId": "123456",
        "terminalId": "1",
    },
    "error_list": [
        {
            "error_code": "0330",
            "description": "No hay transacciones que coincidan con los campos de busqueda",
        }
    ],
}

mobile_payments_success_response = {
    "merchant_identify": {
        "integratorId": 31,
        "merchantId": "123456",
        "terminalId": "1",
    },
    "transaction_list": [
        {
            "trx_date": "2021-06-29",
            "trx_type": "compra",
            "authorization_code": "003823",
            "payment_reference": 118060003823,
            "invoice_number": "0123456789012345",
            "payment_method": "c2p",
            "origin_mobile_number": "encrypted-mobile-number",
            "destination_mobile_number": "encrypted-destination-number",
            "destination_id": "encrypted-destination-id",
            "currency": "ves",
            "amount": 3333.0,
            "destination_bank_id": 105,
        }
    ],
}
