"""waghost — headless WhatsApp OTP requester and registration client."""
from .core import (
    STATE_FILE,
    BadToken,
    RateLimited,
    WAError,
    base_fields,
    is_registered,
    load_state,
    register,
    request_code,
    reset_state,
)

__version__ = "1.0.0"

__all__ = [
    "__version__",
    "STATE_FILE",
    "WAError",
    "RateLimited",
    "BadToken",
    "base_fields",
    "is_registered",
    "load_state",
    "register",
    "request_code",
    "reset_state",
]