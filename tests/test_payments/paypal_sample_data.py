capture_order_sample_response = {
    "id": "3WP397133P813313Y",
    "status": "COMPLETED",
    "payment_source": {
        "paypal": {
            "email_address": "sb-vqn43v17874245@personal.example.com",
            "account_id": "3MXJMBMRBUDRW",
            "name": {"given_name": "John", "surname": "Doe"},
            "address": {"country_code": "VE"},
        }
    },
    "purchase_units": [
        {
            "reference_id": "default",
            "shipping": {
                "name": {"full_name": "John Doe"},
                "address": {
                    "address_line_1": "Free Trade Zone",
                    "admin_area_2": "Caracas",
                    "admin_area_1": "Caracas",
                    "postal_code": "1012",
                    "country_code": "VE",
                },
            },
            "payments": {
                "captures": [
                    {
                        "id": "7WC46909KM139480X",
                        "status": "COMPLETED",
                        "amount": {"currency_code": "USD", "value": "20.00"},
                        "final_capture": True,
                        "seller_protection": {
                            "status": "ELIGIBLE",
                            "dispute_categories": [
                                "ITEM_NOT_RECEIVED",
                                "UNAUTHORIZED_TRANSACTION",
                            ],
                        },
                        "seller_receivable_breakdown": {
                            "gross_amount": {"currency_code": "USD", "value": "20.00"},
                            "paypal_fee": {"currency_code": "USD", "value": "1.38"},
                            "net_amount": {"currency_code": "USD", "value": "18.62"},
                        },
                        "custom_id": "3",
                        "links": [
                            {
                                "href": "https://api.sandbox.paypal.com/v2/payments/captures/7WC46909KM139480X",
                                "rel": "self",
                                "method": "GET",
                            },
                            {
                                "href": "https://api.sandbox.paypal.com/v2/payments/captures/7WC46909KM139480X/refund",
                                "rel": "refund",
                                "method": "POST",
                            },
                            {
                                "href": "https://api.sandbox.paypal.com/v2/checkout/orders/3WP397133P813313Y",
                                "rel": "up",
                                "method": "GET",
                            },
                        ],
                        "create_time": "2023-02-02T14:19:32Z",
                        "update_time": "2023-02-02T14:19:32Z",
                    }
                ]
            },
        }
    ],
    "payer": {
        "name": {"given_name": "John", "surname": "Doe"},
        "email_address": "sb-vqn43v17874245@personal.example.com",
        "payer_id": "3MXJMBMRBUDRW",
        "address": {"country_code": "VE"},
    },
    "links": [
        {
            "href": "https://api.sandbox.paypal.com/v2/checkout/orders/3WP397133P813313Y",
            "rel": "self",
            "method": "GET",
        }
    ],
}

order_details_sample = {
    "id": "8RT61766EM854483G",
    "intent": "CAPTURE",
    "status": "CREATED",
    "purchase_units": [
        {
            "reference_id": "default",
            "amount": {"currency_code": "USD", "value": "20.00"},
            "payee": {
                "email_address": "sb-toh2m17856452@business.example.com",
                "merchant_id": "6X5683BZC4RLW",
            },
            "custom_id": "1",
        }
    ],
    "create_time": "2023-12-06T14:25:54Z",
    "links": [
        {
            "href": "https://api.sandbox.paypal.com/v2/checkout/orders/8RT61766EM854483G",
            "rel": "self",
            "method": "GET",
        },
        {
            "href": "https://www.sandbox.paypal.com/checkoutnow?token=8RT61766EM854483G",
            "rel": "approve",
            "method": "GET",
        },
        {
            "href": "https://api.sandbox.paypal.com/v2/checkout/orders/8RT61766EM854483G",
            "rel": "update",
            "method": "PATCH",
        },
        {
            "href": "https://api.sandbox.paypal.com/v2/checkout/orders/8RT61766EM854483G/capture",
            "rel": "capture",
            "method": "POST",
        },
    ],
}

capture_order_error = {
    "name": "RESOURCE_NOT_FOUND",
    "details": [
        {
            "issue": "INVALID_RESOURCE_ID",
            "description": "Specified resource ID does not exist. Please check the resource ID and try again.",
        }
    ],
    "message": "The specified resource does not exist.",
    "debug_id": "8cf43623bb135",
    "links": [
        {
            "href": "https://developer.paypal.com/docs/api/orders/v2/#error-INVALID_RESOURCE_ID",
            "rel": "information_link",
            "method": "GET",
        }
    ],
}
