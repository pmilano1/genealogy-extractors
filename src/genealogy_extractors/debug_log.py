"""
Consistent Debug Logging for Genealogy Extractors

Usage:
    from debug_log import debug, info, warn, error, set_verbose

All output follows these patterns:
    debug(source, msg)  -> [SOURCE] message (only in verbose mode)
    info(msg)           -> message (always shown)
    warn(source, msg)   -> [SOURCE] ⚠️  message
    error(source, msg)  -> [SOURCE] ❌ message
"""

_verbose = False


def set_verbose(enabled: bool):
    """Enable/disable verbose output globally."""
    global _verbose
    _verbose = enabled


def is_verbose() -> bool:
    """Check if verbose mode is enabled."""
    return _verbose


def debug(source: str, message: str):
    """Print debug message (only in verbose mode). Format: [SOURCE] message"""
    if _verbose:
        print(f"[{source}] {message}")


def info(message: str):
    """Print info message (always shown)."""
    print(message)


def warn(source: str, message: str):
    """Print warning message. Format: [SOURCE] ⚠️  message"""
    print(f"[{source}] ⚠️  {message}")


def error(source: str, message: str):
    """Print error message. Format: [SOURCE] ❌ message"""
    print(f"[{source}] ❌ {message}")

