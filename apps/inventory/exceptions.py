class InsufficientStockError(Exception):
    """Not enough stock exists anywhere reachable to satisfy the request.
    A genuine business-rule violation -- maps to HTTP 422."""


class StockLevelChangedError(Exception):
    """A concurrent operation changed the stock level between this
    operation's read and its conditional write. The caller should retry.
    Maps to HTTP 409."""


class ApprovalRequiredError(Exception):
    """An operation (e.g. recording lost stock) requires Supervisor sign-off
    that wasn't provided. Maps to HTTP 400/403."""
