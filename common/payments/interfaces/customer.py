class Customer:
    id: None
    name: None
    lastname: None
    email: None
    description: None
    areacode: None
    phone: None
    birthday: None

    def save_stripe_customer(self, data):
        self.id = data.id


class CustomerDTO:
    uid: None
