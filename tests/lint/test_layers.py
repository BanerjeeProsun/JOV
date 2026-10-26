"""Architectural Lint: Test layer boundary enforcement via AST parsing.

Rules from Blueprint v2.0 Section 4:
- domain/ imports NOTHING from api, worker, services, or adapters.
- services/ imports domain, ports, adapters/db (for models/session), but NOT api, worker.
- adapters/ imports domain, ports, config, but NOT api, worker.
"""

import ast
from pathlib import Path
import pytest


def get_imports(py_file: Path) -> list[str]:
    """Parse python source and extract imported module names."""
    with open(py_file, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=str(py_file))
    
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports


def test_domain_layer_isolation() -> None:
    """The domain layer must be pure Python with zero imports from other jovsi packages."""
    domain_dir = Path("src/jovsi/domain")
    assert domain_dir.exists()

    forbidden_prefixes = (
        "jovsi.api",
        "jovsi.worker",
        "jovsi.services",
        "jovsi.adapters",
        "fastapi",
        "playwright",
        "sqlalchemy",
    )

    violations = []
    for py_file in domain_dir.glob("*.py"):
        if py_file.name == "__init__.py":
            continue
        imports = get_imports(py_file)
        for imp in imports:
            for forbidden in forbidden_prefixes:
                if imp == forbidden or imp.startswith(f"{forbidden}."):
                    violations.append(f"{py_file.name} imports forbidden '{imp}'")

    assert not violations, f"Domain boundary violations detected: {violations}"
