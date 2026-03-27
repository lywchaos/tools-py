# cc-project-init Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a CLI tool that detects project context and idempotently manages a generated instructions block in CLAUDE.md.

**Architecture:** A `rules.py` module defines detection rules as dataclasses with detect functions and instruction text. A `cli.py` module orchestrates: run rules, build content block, check idempotency via regex sentinels, preview, confirm, write. Single-command typer app.

**Tech Stack:** Python 3.12, typer (existing dep), stdlib (pathlib, re, dataclasses)

---

### Task 1: Rule Engine (`rules.py`)

**Files:**
- Create: `src/tools_py/cc_project_init/__init__.py`
- Create: `src/tools_py/cc_project_init/rules.py`
- Create: `tests/cc_project_init/test_rules.py`

- [ ] **Step 1: Create module package**

Create the empty `__init__.py`:

```python
```

- [ ] **Step 2: Write failing tests for Rule dataclass and detection functions**

```python
from pathlib import Path

from tools_py.cc_project_init.rules import ALL_RULES, Rule, detect_rules


def test_rule_dataclass():
    rule = Rule(name="test", detect=lambda root: True, instructions="# Test")
    assert rule.name == "test"
    assert rule.detect(Path(".")) is True
    assert rule.instructions == "# Test"


def test_detect_rules_uv(tmp_path: Path):
    (tmp_path / "uv.lock").touch()
    matched = detect_rules(tmp_path)
    names = [r.name for r in matched]
    assert "uv" in names


def test_detect_rules_python(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = \"foo\"\n")
    matched = detect_rules(tmp_path)
    names = [r.name for r in matched]
    assert "python" in names


def test_detect_rules_python_no_project_section(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n")
    matched = detect_rules(tmp_path)
    names = [r.name for r in matched]
    assert "python" not in names


def test_detect_rules_node(tmp_path: Path):
    (tmp_path / "package.json").write_text("{}")
    matched = detect_rules(tmp_path)
    names = [r.name for r in matched]
    assert "node" in names


def test_detect_rules_go(tmp_path: Path):
    (tmp_path / "go.mod").touch()
    matched = detect_rules(tmp_path)
    names = [r.name for r in matched]
    assert "go" in names


def test_detect_rules_no_match(tmp_path: Path):
    matched = detect_rules(tmp_path)
    assert matched == []


def test_detect_rules_multiple_match(tmp_path: Path):
    (tmp_path / "uv.lock").touch()
    (tmp_path / "pyproject.toml").write_text("[project]\nname = \"foo\"\n")
    matched = detect_rules(tmp_path)
    names = [r.name for r in matched]
    assert "uv" in names
    assert "python" in names
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/cc_project_init/test_rules.py -v`
Expected: FAIL — module not found

- [ ] **Step 4: Implement rules.py**

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/cc_project_init/test_rules.py -v`
Expected: All 8 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/tools_py/cc_project_init/__init__.py src/tools_py/cc_project_init/rules.py tests/cc_project_init/test_rules.py
git commit -m "feat(cc-project-init): add rule engine with initial detection rules"
```

---

### Task 2: CLAUDE.md Writer with Idempotency

**Files:**
- Create: `src/tools_py/cc_project_init/writer.py`
- Create: `tests/cc_project_init/test_writer.py`

- [ ] **Step 1: Write failing tests for the writer module**

```python
from pathlib import Path

from tools_py.cc_project_init.writer import build_block, update_claude_md

SENTINEL_START = "<!-- USER INSTRUCTIONS START -->"
SENTINEL_END = "<!-- USER INSTRUCTIONS END -->"


def test_build_block():
    instructions = ["## Tool: uv\n- Use uv run", "## Lang: Python\n- PEP 8"]
    block = build_block(instructions)
    assert block.startswith(SENTINEL_START)
    assert block.endswith(SENTINEL_END)
    assert "# Project Environment" in block
    assert "## Tool: uv" in block
    assert "## Lang: Python" in block


def test_update_claude_md_append_to_empty(tmp_path: Path):
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("")
    block = f"{SENTINEL_START}\n# Project Environment\n\ncontent\n{SENTINEL_END}"
    result = update_claude_md(claude_md, block)
    assert SENTINEL_START in result
    assert "content" in result


def test_update_claude_md_append_to_existing(tmp_path: Path):
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("# My Project\n\nExisting content.\n")
    block = f"{SENTINEL_START}\n# Project Environment\n\ncontent\n{SENTINEL_END}"
    result = update_claude_md(claude_md, block)
    assert result.startswith("# My Project\n\nExisting content.\n")
    assert result.endswith(block)


def test_update_claude_md_replace_existing_block(tmp_path: Path):
    claude_md = tmp_path / "CLAUDE.md"
    old_content = (
        "# My Project\n\n"
        f"{SENTINEL_START}\nold stuff\n{SENTINEL_END}\n\n"
        "# Footer\n"
    )
    claude_md.write_text(old_content)
    block = f"{SENTINEL_START}\n# Project Environment\n\nnew stuff\n{SENTINEL_END}"
    result = update_claude_md(claude_md, block)
    assert "old stuff" not in result
    assert "new stuff" in result
    assert "# My Project" in result
    assert "# Footer" in result


def test_update_claude_md_create_if_missing(tmp_path: Path):
    claude_md = tmp_path / "CLAUDE.md"
    block = f"{SENTINEL_START}\ncontent\n{SENTINEL_END}"
    result = update_claude_md(claude_md, block)
    assert SENTINEL_START in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/cc_project_init/test_writer.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement writer.py**

```python
import re
from pathlib import Path

SENTINEL_START = "<!-- USER INSTRUCTIONS START -->"
SENTINEL_END = "<!-- USER INSTRUCTIONS END -->"
SENTINEL_PATTERN = re.compile(
    re.escape(SENTINEL_START) + r".*?" + re.escape(SENTINEL_END),
    re.DOTALL,
)


def build_block(instructions: list[str]) -> str:
    body = "\n\n".join(instructions)
    return f"{SENTINEL_START}\n# Project Environment\n\n{body}\n{SENTINEL_END}"


def update_claude_md(claude_md_path: Path, block: str) -> str:
    if claude_md_path.exists():
        content = claude_md_path.read_text()
    else:
        content = ""

    if SENTINEL_PATTERN.search(content):
        return SENTINEL_PATTERN.sub(block, content)

    if content and not content.endswith("\n"):
        content += "\n"

    separator = "\n" if content else ""
    return content + separator + block
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/cc_project_init/test_writer.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/tools_py/cc_project_init/writer.py tests/cc_project_init/test_writer.py
git commit -m "feat(cc-project-init): add CLAUDE.md writer with idempotent sentinel logic"
```

---

### Task 3: CLI Entry Point

**Files:**
- Create: `src/tools_py/cc_project_init/cli.py`
- Modify: `pyproject.toml:15-17` (add script entry)
- Create: `tests/cc_project_init/test_cli.py`

- [ ] **Step 1: Write failing tests for the CLI**

```python
from pathlib import Path

from typer.testing import CliRunner

from tools_py.cc_project_init.cli import app

runner = CliRunner()

SENTINEL_START = "<!-- USER INSTRUCTIONS START -->"
SENTINEL_END = "<!-- USER INSTRUCTIONS END -->"


def test_cli_no_rules_match(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app)
    assert result.exit_code == 0
    assert "No matching rules" in result.output


def test_cli_detects_and_previews(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "uv.lock").touch()
    (tmp_path / "pyproject.toml").write_text("[project]\nname = \"test\"\n")
    result = runner.invoke(app, input="n\n")
    assert "uv" in result.output.lower()
    assert SENTINEL_START in result.output


def test_cli_writes_claude_md(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "uv.lock").touch()
    result = runner.invoke(app, input="y\n")
    assert result.exit_code == 0
    claude_md = tmp_path / "CLAUDE.md"
    assert claude_md.exists()
    content = claude_md.read_text()
    assert SENTINEL_START in content
    assert "uv" in content.lower()


def test_cli_idempotent_rerun(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "uv.lock").touch()
    runner.invoke(app, input="y\n")
    runner.invoke(app, input="y\n")
    content = (tmp_path / "CLAUDE.md").read_text()
    assert content.count(SENTINEL_START) == 1


def test_cli_preserves_existing_content(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("# My Project\n\nKeep this.\n")
    (tmp_path / "go.mod").touch()
    runner.invoke(app, input="y\n")
    content = claude_md.read_text()
    assert "# My Project" in content
    assert "Keep this." in content
    assert SENTINEL_START in content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/cc_project_init/test_cli.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement cli.py**

```python
from pathlib import Path

import typer

from tools_py.cc_project_init.rules import detect_rules
from tools_py.cc_project_init.writer import build_block, update_claude_md

app = typer.Typer(help="Detect project context and generate CLAUDE.md instructions")


@app.callback(invoke_without_command=True)
def init():
    """Detect project context and update CLAUDE.md with environment instructions."""
    project_root = Path.cwd()
    claude_md_path = project_root / "CLAUDE.md"

    matched = detect_rules(project_root)
    if not matched:
        typer.echo("No matching rules found for this project.")
        return

    typer.echo(f"Detected: {', '.join(r.name for r in matched)}\n")

    block = build_block([r.instructions for r in matched])
    new_content = update_claude_md(claude_md_path, block)

    typer.echo("--- Preview ---")
    typer.echo(block)
    typer.echo("--- End Preview ---\n")

    if not typer.confirm("Apply these changes to CLAUDE.md?"):
        typer.echo("Aborted.")
        raise typer.Exit()

    claude_md_path.write_text(new_content)
    typer.echo(f"Updated {claude_md_path}")


def main():
    app()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/cc_project_init/test_cli.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Register entry point in pyproject.toml**

Add `cc-project-init` to the `[project.scripts]` section:

```toml
[project.scripts]
linky = "tools_py.symlink.cli:main"
llm-call = "tools_py.llm_call.cli:main"
cc-project-init = "tools_py.cc_project_init.cli:main"
```

- [ ] **Step 6: Reinstall and verify CLI works**

Run: `uv sync && cc-project-init --help`
Expected: Shows help text with description "Detect project context and generate CLAUDE.md instructions"

- [ ] **Step 7: Commit**

```bash
git add src/tools_py/cc_project_init/cli.py tests/cc_project_init/test_cli.py pyproject.toml
git commit -m "feat(cc-project-init): add CLI entry point with preview and confirm"
```

---

### Task 4: Run All Tests and Final Verification

**Files:** None (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest tests/ -v`
Expected: All 18 tests PASS

- [ ] **Step 2: Manual smoke test**

Run: `cd /tmp && mkdir test-project && cd test-project && touch uv.lock && echo '[project]\nname = "demo"' > pyproject.toml && cc-project-init`
Expected: Detects uv + python, shows preview, prompts for confirm. After confirming, CLAUDE.md is created with the sentinel block.

- [ ] **Step 3: Verify idempotency manually**

Run `cc-project-init` again in the same directory.
Expected: Replaces the block, CLAUDE.md has exactly one sentinel block.

- [ ] **Step 4: Commit any fixes if needed**
