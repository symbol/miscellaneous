class TransactionSnapshot():
    # pylint: disable=too-many-instance-attributes

    def __init__(self, address, tag):
        self.address = address
        self.tag = tag

        self.timestamp = None
        self.amount = 0
        self.height = 0
        self.fee_paid = 0
        self.collation_id = 0
        self.comments = None
        self.hash = None
