"""AST-based import whitelist — fast first-pass reject before Docker execution."""

from __future__ import annotations

import ast

ALLOWED_MODULES = {
    "pandas",
    "numpy",
    "matplotlib",
    "matplotlib.pyplot",
    "scipy",
    "statsmodels",
    "sklearn",
    "math",
    "statistics",
    "datetime",
    "json",
}


class DisallowedImportError(Exception):
    """Raised when generated code imports a module outside the whitelist."""


def check_imports(code: str) -> None:
    """Parse `code` and raise DisallowedImportError on any non-whitelisted import."""
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if alias.name not in ALLOWED_MODULES and root not in ALLOWED_MODULES:
                    raise DisallowedImportError(f"Import not allowed: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                raise DisallowedImportError("Relative imports are not allowed")
            root = node.module.split(".")[0]
            if node.module not in ALLOWED_MODULES and root not in ALLOWED_MODULES:
                raise DisallowedImportError(f"Import not allowed: {node.module}")
