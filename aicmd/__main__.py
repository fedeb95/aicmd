# Support being executed both as a package (python -m aicmd) and as a module after install.
# Try a relative import, fall back to absolute import to avoid "attempted relative import with no known parent package" errors.
try:
    from .cli import app
except Exception:
    from aicmd.cli import app
