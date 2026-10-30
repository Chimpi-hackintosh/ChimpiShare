class ShareError(Exception):
    """A stable, localizable error, including across the wire."""

    def __init__(self, code, **values):
        self.code = code
        self.values = values
        super().__init__(code)
