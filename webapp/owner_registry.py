# In-memory registry of owner display name → email address.
# Populated during document parsing; read by notification routes.
# Keys are stored lowercased for case-insensitive lookup.
from typing import Optional

_registry: dict = {}


def register(name: str, email: str) -> None:
    """Store a name→email mapping discovered from a mailto: link."""
    if name and email:
        _registry[name.strip().lower()] = email.strip()


def lookup(name: str) -> Optional[str]:
    """Return the email for a given owner display name, or None if unknown."""
    if not name:
        return None
    return _registry.get(name.strip().lower())
