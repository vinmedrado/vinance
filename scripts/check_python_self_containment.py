from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ModuleSource:
    module: str
    path: Path
    is_package: bool
    tree: ast.Module
    exports: frozenset[str]


@dataclass(frozen=True)
class ImportProblem:
    path: Path
    line: int
    reference: str
    reason: str


@dataclass(frozen=True)
class ActiveImportProblem:
    module: str
    detail: str


def _tracked_python_paths() -> list[Path]:
    try:
        result = subprocess.run(
            ["git", "ls-files", "--", "*.py"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        ignored_parts = {
            ".git",
            ".venv",
            "__pycache__",
            "node_modules",
            "dist",
            "_archived",
        }
        return sorted(
            path
            for path in ROOT.rglob("*.py")
            if not ignored_parts.intersection(path.relative_to(ROOT).parts)
        )
    return [ROOT / line for line in result.stdout.splitlines() if line]


def _stdin_python_paths() -> list[Path]:
    return [ROOT / line.strip() for line in sys.stdin if line.strip()]


def _module_name(path: Path) -> tuple[str, bool]:
    relative = path.relative_to(ROOT)
    parts = list(relative.with_suffix("").parts)
    is_package = parts[-1] == "__init__"
    if is_package:
        parts.pop()
    return ".".join(parts), is_package


def _bound_names(tree: ast.Module) -> frozenset[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if alias.name == "*":
                    continue
                names.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
    return frozenset(names)


def load_modules(paths: list[Path]) -> tuple[dict[str, ModuleSource], list[str]]:
    modules: dict[str, ModuleSource] = {}
    syntax_errors: list[str] = []
    for path in paths:
        try:
            source = path.read_text(encoding="utf-8-sig")
            tree = ast.parse(source, filename=str(path))
        except (OSError, SyntaxError, UnicodeError) as exc:
            syntax_errors.append(f"{path.relative_to(ROOT).as_posix()}: {exc}")
            continue
        module, is_package = _module_name(path)
        modules[module] = ModuleSource(
            module=module,
            path=path,
            is_package=is_package,
            tree=tree,
            exports=_bound_names(tree),
        )

    # Compatibility modules may intentionally re-export a canonical module
    # with ``from ... import *``. Resolve those tracked re-exports so callers
    # are not reported as broken merely because the wrapper is declarative.
    exports = {module: set(source.exports) for module, source in modules.items()}
    changed = True
    while changed:
        changed = False
        for module, source in modules.items():
            for node in ast.walk(source.tree):
                if not isinstance(node, ast.ImportFrom):
                    continue
                if not any(alias.name == "*" for alias in node.names):
                    continue
                target = _resolve_from(source, node)
                if target not in exports:
                    continue
                previous_size = len(exports[module])
                exports[module].update(exports[target])
                changed = changed or len(exports[module]) != previous_size
    modules = {
        module: ModuleSource(
            module=source.module,
            path=source.path,
            is_package=source.is_package,
            tree=source.tree,
            exports=frozenset(exports[module]),
        )
        for module, source in modules.items()
    }
    return modules, syntax_errors


def _resolve_from(source: ModuleSource, node: ast.ImportFrom) -> str:
    if node.level == 0:
        return node.module or ""
    package = source.module if source.is_package else source.module.rpartition(".")[0]
    package_parts = package.split(".") if package else []
    if node.level > len(package_parts):
        return ""
    anchor = package_parts[: len(package_parts) - node.level + 1]
    if node.module:
        anchor.extend(node.module.split("."))
    return ".".join(anchor)


def find_internal_import_problems(
    modules: dict[str, ModuleSource],
) -> list[ImportProblem]:
    module_names = set(modules)
    internal_roots = {
        name
        for name, source in modules.items()
        if name and "." not in name and (source.is_package or source.path.parent == ROOT)
    }
    # ``backend`` is intentionally a PEP 420 namespace package in this
    # repository.  It is still an internal import root even without a tracked
    # backend/__init__.py.  Do not infer every top-level directory this way:
    # the historical ``alembic/`` directory would otherwise shadow the real
    # third-party Alembic package during static analysis.
    internal_roots.add("backend")

    def module_exists(name: str) -> bool:
        return name in module_names or any(
            candidate.startswith(f"{name}.") for candidate in module_names
        )

    problems: list[ImportProblem] = []
    for source in modules.values():
        for node in ast.walk(source.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    reference = alias.name
                    if reference.split(".", 1)[0] in internal_roots and not module_exists(
                        reference
                    ):
                        problems.append(
                            ImportProblem(
                                path=source.path,
                                line=node.lineno,
                                reference=reference,
                                reason="internal module does not exist",
                            )
                        )
            elif isinstance(node, ast.ImportFrom):
                base = _resolve_from(source, node)
                if not base:
                    if node.level:
                        problems.append(
                            ImportProblem(
                                path=source.path,
                                line=node.lineno,
                                reference="." * node.level + (node.module or ""),
                                reason="relative import escapes the tracked package",
                            )
                        )
                    continue
                if base.split(".", 1)[0] not in internal_roots:
                    continue
                if not module_exists(base):
                    problems.append(
                        ImportProblem(
                            path=source.path,
                            line=node.lineno,
                            reference=base,
                            reason="internal module does not exist",
                        )
                    )
                    continue
                base_exports = modules.get(base)
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    candidate = f"{base}.{alias.name}"
                    if module_exists(candidate):
                        continue
                    if base_exports is not None and alias.name in base_exports.exports:
                        continue
                    problems.append(
                        ImportProblem(
                            path=source.path,
                            line=node.lineno,
                            reference=f"{base}:{alias.name}",
                            reason="name is not exported by the tracked internal module",
                        )
                    )
    return sorted(
        problems,
        key=lambda problem: (problem.path.as_posix(), problem.line, problem.reference),
    )


def _active_import(module: str) -> ActiveImportProblem | None:
    command = (
        "import importlib; "
        f"importlib.import_module({module!r})"
    )
    try:
        result = subprocess.run(
            [sys.executable, "-c", command],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return ActiveImportProblem(module=module, detail="timed out after 30 seconds")
    if result.returncode == 0:
        return None
    detail_lines = (result.stderr or result.stdout).strip().splitlines()
    detail = detail_lines[-1] if detail_lines else f"exit code {result.returncode}"
    return ActiveImportProblem(module=module, detail=detail)


def find_active_import_problems(
    modules: dict[str, ModuleSource], prefixes: tuple[str, ...]
) -> list[ActiveImportProblem]:
    candidates = sorted(
        module
        for module in modules
        if module
        and any(module == prefix or module.startswith(f"{prefix}.") for prefix in prefixes)
        and ".tests." not in module
        and not module.startswith("backend.tests.")
        and ".alembic." not in module
    )
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(_active_import, candidates))
    return [problem for problem in results if problem is not None]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate syntax and internal imports for tracked Python sources."
    )
    parser.add_argument(
        "--paths-stdin",
        action="store_true",
        help="read repository-relative Python paths from stdin instead of invoking git",
    )
    parser.add_argument(
        "--active-prefix",
        action="append",
        default=[],
        help=(
            "actively import modules under this prefix in isolated subprocesses; "
            "may be repeated"
        ),
    )
    arguments = parser.parse_args()

    paths = _stdin_python_paths() if arguments.paths_stdin else _tracked_python_paths()
    modules, syntax_errors = load_modules(paths)
    problems = find_internal_import_problems(modules)
    active_problems = find_active_import_problems(
        modules, tuple(arguments.active_prefix)
    ) if arguments.active_prefix else []

    print(f"TRACKED_PYTHON_FILES={len(paths)}")
    print(f"PARSED_PYTHON_MODULES={len(modules)}")
    print(f"SYNTAX_ERRORS={len(syntax_errors)}")
    print(f"BROKEN_INTERNAL_IMPORTS={len(problems)}")
    print(f"ACTIVE_IMPORT_FAILURES={len(active_problems)}")
    for error in syntax_errors:
        print(f"SYNTAX {error}")
    for problem in problems:
        relative = problem.path.relative_to(ROOT).as_posix()
        print(
            f"IMPORT {relative}:{problem.line} {problem.reference} "
            f"({problem.reason})"
        )
    for problem in active_problems:
        print(f"ACTIVE {problem.module} ({problem.detail})")
    return 1 if syntax_errors or problems or active_problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
