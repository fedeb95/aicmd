"""Top-level package for aicmd.

Package metadata.
"""

# No eager imports to avoid circular dependencies.

# Lazy import to expose submodule and functions without eager execution
from importlib import import_module as _import_module
providers = _import_module('.providers', __name__)
services = _import_module('.services', __name__)

summarize_text = services.summarize_text
describe_image = services.describe_image
rewrite_text = services.rewrite_text

__all__ = ["providers", "summarize_text", "describe_image", "rewrite_text"]
