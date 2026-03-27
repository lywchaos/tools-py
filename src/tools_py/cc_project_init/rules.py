from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass
class Rule:
    name: str
    detect: Callable[[Path], bool]
    instructions: str


def _detect_uv(root: Path) -> bool:
    return (root / "uv.lock").exists()


def _detect_python(root: Path) -> bool:
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return False
    return "[project]" in pyproject.read_text()


def _detect_node(root: Path) -> bool:
    return (root / "package.json").exists()


def _detect_go(root: Path) -> bool:
    return (root / "go.mod").exists()


ALL_RULES: list[Rule] = [
    Rule(
        name="uv",
        detect=_detect_uv,
        instructions=(
            "## Package Manager: uv\n"
            "- Use `uv run python` to invoke Python instead of bare `python`\n"
            "- Use `uv run pytest` to run tests\n"
            "- Use `uv add <package>` to add dependencies\n"
            "- Do NOT use `pip install` directly"
        ),
    ),
    Rule(
        name="python",
        detect=_detect_python,
        instructions=(
            "## Language: Python\n"
            "- Follow PEP 8 conventions\n"
            "- Use type hints for function signatures"
        ),
    ),
    Rule(
        name="node",
        detect=_detect_node,
        instructions=(
            "## Language: Node.js\n"
            "- Check for lockfile (package-lock.json, yarn.lock, pnpm-lock.yaml) to determine package manager"
        ),
    ),
    Rule(
        name="go",
        detect=_detect_go,
        instructions=(
            "## Language: Go\n"
            "- Use `go mod tidy` to manage dependencies\n"
            "- Use `go test ./...` to run tests"
        ),
    ),
]


def detect_rules(root: Path) -> list[Rule]:
    return [rule for rule in ALL_RULES if rule.detect(root)]
