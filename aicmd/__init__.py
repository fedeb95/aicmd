"""Top-level package for aicmd.

Package metadata.
"""

# No eager imports to avoid circular dependencies.

# Lazy import to expose submodule without eager execution
from importlib import import_module as _import_module
providers = _import_module('.providers', __name__)

__all__ = ["providers"]
