"""Idempotency services for upload batches."""

CONFLICT_FIELDS = (
    "source_type",
    "source_account_id",
    "archive_sha256",
    "archive_size",
)


def _idempotency_conflicts(batch, values):
    for field in CONFLICT_FIELDS:
        declared = values.get(field)
        if field in ("source_account_id", "archive_sha256") and not declared:
            # Optional values that the retry did not send never conflict.
            continue
        if field == "archive_size" and declared is None:
            continue
        stored = getattr(batch, field)
        if field == "archive_sha256":
            declared = declared.lower()
            stored = (stored or "").lower()
        if stored != declared:
            return True
    return False
