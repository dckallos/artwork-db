#!/usr/bin/env python3
"""
Static validation of the artwork_orchestration package WITHOUT importing dagster.

For every module, parse the AST, collect top-level defined names (functions, classes,
assignments, imports). Then for every intra-package `from .X import a, b` verify that
a, b actually exist as top-level names in X.py. Also flag any reference to the deleted
fork modules. Exits non-zero on any problem.
"""
import ast
import pathlib
import sys

PKG = pathlib.Path(__file__).resolve().parent / "orchestration" / "artwork_orchestration"
DELETED = {"checks", "asset_checks", "sf_introspect", "partitions"}

def toplevel_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    names.add(t.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                names.add(a.asname or a.name.split(".")[0])
    return names

modules = {p.stem: ast.parse(p.read_text(), filename=p.name) for p in PKG.glob("*.py")}
exports = {name: toplevel_names(tree) for name, tree in modules.items()}

problems: list[str] = []
for name, tree in modules.items():
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module:
            target = node.module.split(".")[0]
            if target in DELETED:
                problems.append(f"{name}.py imports DELETED module '{target}'")
                continue
            if target in exports:
                for a in node.names:
                    if a.name != "*" and a.name not in exports[target]:
                        problems.append(
                            f"{name}.py: `from .{target} import {a.name}` -> "
                            f"'{a.name}' NOT defined in {target}.py"
                        )
        # bare `from . import X`
        if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module is None:
            for a in node.names:
                if a.name in DELETED:
                    problems.append(f"{name}.py does `from . import {a.name}` (DELETED)")

print(f"modules checked: {sorted(modules)}")
if problems:
    print("VALIDATION FAILED:")
    for p in problems:
        print("  -", p)
    sys.exit(1)
print("VALIDATION OK: all intra-package imports resolve; no references to deleted modules.")
