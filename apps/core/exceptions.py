class ImmutableRecordError(Exception):
    """Raised when code attempts to modify or delete an append-only record
    (AuditLog, InventoryTransaction, ...). These records are historical facts;
    corrections must be made by posting a new reversing/compensating record."""
