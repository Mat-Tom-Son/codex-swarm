import uuid

try:
    from python_ulid import ULID  # type: ignore
except ImportError:
    ULID = None


def new_id(prefix: str) -> str:
    if ULID:
        suffix = ULID().str.lower()
    else:
        suffix = uuid.uuid4().hex
    return f"{prefix}-{suffix}"
