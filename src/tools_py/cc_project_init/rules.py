from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass
class Rule:
    name: str
    detect: Callable[[Path], bool]
    instructions: str


def _detect_common(root: Path) -> bool:
    return True


def _detect_uv(root: Path) -> bool:
    return (root / "uv.lock").exists()


def _detect_python(root: Path) -> bool:
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return False
    return "[project]" in pyproject.read_text()


ALL_RULES: list[Rule] = [
    Rule(
        name="common-instructions",
        detect=_detect_common,
        instructions=(
            "## Common instructions\n"
            "- Never force-add ignored files (for example with `git add -f`) unless the user explicitly asks for that exact behavior.\n"
        ),
    ),
    Rule(
        name="uv",
        detect=_detect_uv,
        instructions=(
            "## Package Manager: uv\n"
            "uv is used so:\n"
            "- Use `uv run python` to invoke Python\n"
            "- Use `uv run python -m <some-module>` to run python module cli tools like pytest\n"
        ),
    ),
    Rule(
        name="python",
        detect=_detect_python,
        instructions=(
            "## Language: Python\n"
            "- Use `typer` when building cli\n"
            "- Use `pydantic` for data validation models\n"
        ),
    ),
]


def detect_rules(root: Path) -> list[Rule]:
    return [rule for rule in ALL_RULES if rule.detect(root)]
