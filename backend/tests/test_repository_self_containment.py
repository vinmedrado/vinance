from __future__ import annotations

from pathlib import Path
import subprocess

from scripts.check_python_self_containment import (
    find_internal_import_problems,
    load_modules,
)


ROOT = Path(__file__).resolve().parents[2]


def _repository_python_paths() -> list[Path]:
    try:
        result = subprocess.run(
            [
                "git",
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "--",
                "*.py",
            ],
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


def test_repository_python_sources_are_syntactically_self_contained() -> None:
    modules, syntax_errors = load_modules(_repository_python_paths())
    import_problems = find_internal_import_problems(modules)

    assert syntax_errors == []
    assert import_problems == []
