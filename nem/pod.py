import datetime


class PriceSnapshot():
    def __init__(self, date):
        self.date = date
        self.price = 0
        self.volume = 0
        self.market_cap = 0
        self.comments = None

    def fix_types(self):
        self.date = datetime.datetime.fromisoformat(self.date).date()

        self.price = float(self.price)
        self.volume = float(self.volume)
        self.market_cap = float(self.market_cap)


class TransactionSnapshot():
    # pylint: disable=too-many-instance-attributes

    def __init__(self, address, tag):
        self.address = address
        self.tag = tag

        self.timestamp = None

        self.amount = 0
        self.fee_paid = 0
        self.height = 0

        self.collation_id = 0
        self.comments = None
        self.hash = None

    def fix_types(self, date_only=False):
        self.timestamp = datetime.datetime.fromisoformat(self.timestamp)
        if date_only:
            self.timestamp = self.timestamp.date()

        self.amount = float(self.amount)
        self.fee_paid = float(self.fee_paid)
        self.height = int(self.height)

    def round(self):
        self.amount = round(self.amount, 6)
        self.fee_paid = round(self.fee_paid, 6)


class AugmentedTransactionSnapshot(TransactionSnapshot):
    def __init__(self):
        TransactionSnapshot.__init__(self, None, None)
        self.price = 0.0
        self.fiat_amount = 0.0
        self.fiat_fee_paid = 0.0

    def fix_types(self, date_only=False):
        TransactionSnapshot.fix_types(self, date_only)
        self.price = float(self.price)
        self.fiat_amount = float(self.fiat_amount)
        self.fiat_fee_paid = float(self.fiat_fee_paid)

    def round(self):
        TransactionSnapshot.round(self)
        self.fiat_amount = round(self.fiat_amount, 3)
        self.fiat_fee_paid = round(self.fiat_fee_paid, 3)

    def set_price(self, price):
        self.price = price
        self.fiat_amount = self.amount * self.price
        self.fiat_fee_paid = self.fee_paid * self.price
