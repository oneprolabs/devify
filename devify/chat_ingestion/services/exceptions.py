"""Upload lifecycle and archive validation errors."""


class UploadTransitionError(ValueError):
    """Raised when a batch cannot move to the requested status."""


class ArchiveTooLarge(ValueError):
    """Raised when the archive exceeds the configured size limit."""


class ArchiveMismatch(ValueError):
    """Raised when the archive contradicts a declared checksum or size."""


class ArchiveMissing(ValueError):
    """Raised when a batch is completed without a stored archive."""


class RevokeRejected(ValueError):
    """Raised when an upload may not be withdrawn in its current state."""
