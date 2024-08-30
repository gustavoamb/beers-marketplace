import abc
from .customer import Customer
from .payment_information import PaymentInformation


class PaymentServiceInterface(metaclass=abc.ABCMeta):
    @classmethod
    def __subclasshook__(cls, subclass):
        return (
            hasattr(subclass, "create_customer")
            and callable(subclass.create_customer)
            and hasattr(subclass, "create_payment")
            and callable(subclass.create_payment)
            and hasattr(subclass, "capture_payment")
            and callable(subclass.create_payment)
            or NotImplemented
        )

    @abc.abstractmethod
    def create_customer(self, customer: Customer):
        raise NotImplementedError

    @abc.abstractmethod
    def create_payment(self, payment_information: PaymentInformation):
        raise NotImplementedError

    @abc.abstractmethod
    def capture_payment(self):
        raise NotImplementedError
