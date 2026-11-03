# Security Decorator Layer (autorag-server/utils/decorators.py)

import functools

from app.services.pii_service import mask_pii


def security_masker(func):  # type: ignore[no-untyped-def]
    """
    Decorator that masks PII in all string arguments before calling the wrapped function.

    Handles both plain functions and methods (where args[0] is the 'self' instance).
    Masks all string positional args and all string keyword arg values.

    Bug-fix note: previous version computed cleaned_kwargs but passed the original
    **kwargs to the function, discarding the masking work. Fixed to pass **cleaned_kwargs.
    Also fixed: only args[0] was checked for masking; now ALL positional args are checked.
    """

    @functools.wraps(func)
    async def wrapper(*args: object, **kwargs: object) -> object:
        # Mask all string positional args; leave non-string args (self, integers, etc.) untouched
        new_args = tuple(
            mask_pii(a) if isinstance(a, str) else a  # type: ignore[arg-type]
            for a in args
        )

        # Mask all string keyword arg values
        cleaned_kwargs = {
            k: mask_pii(v) if isinstance(v, str) else v  # type: ignore[arg-type]
            for k, v in kwargs.items()
        }

        return await func(*new_args, **cleaned_kwargs)

    return wrapper
