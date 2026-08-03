class IngestError(Exception):
    """Raised when a source record can't be mapped to the data model.
    Parsers must raise this rather than silently dropping or guessing at
    a record - see the project brief's 'fail loudly and specifically'
    requirement."""
