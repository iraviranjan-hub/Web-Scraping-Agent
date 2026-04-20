class KRAITaxSystemError(Exception):
    """Custom exception raised when KRA iTax shows a system error page or message."""
    def __init__(self, message, error_details=None):
        super().__init__(message)
        self.error_details = error_details
