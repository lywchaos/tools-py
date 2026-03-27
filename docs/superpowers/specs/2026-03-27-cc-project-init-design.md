# cc-project-init Design Spec

## Overview

A CLI module that detects project context by scanning for predefined files (e.g., `uv.lock`, `pyproject.toml`) and idempotently appends generated instructions to the project's `CLAUDE.md`.

## Module Structure

```
src/tools_py/cc_project_init/
├── __init__.py        # empty
├── cli.py             # typer app, single command entry point
└── rules.py           # Rule dataclass + detection rules
```

Entry point in `pyproject.toml`:

```toml
cc-project-init = "tools_py.cc_project_init.cli:main"
```

## Rule Engine

### Rule Dataclass (`rules.py`)

```python
@dataclass
class Rule:
    name: str                          # human-readable label, e.g. "uv"
    detect: Callable[[Path], bool]     # receives project root, returns True if applies
    instructions: str                  # markdown content to inject
```

All rules are collected in a module-level list `ALL_RULES: list[Rule]`. Adding a new rule means appending to this list — no other changes required.

### Initial Rules

| Rule | Signal | Generated Instructions |
|------|--------|----------------------|
| `uv` | `uv.lock` exists in project root | Use `uv run python` to invoke Python; use `uv add` to manage deps |
| `python` | `pyproject.toml` exists with `[project]` section | Python project — follow PEP conventions |
| `node` | `package.json` exists | Node.js project — use appropriate package manager |
| `go` | `go.mod` exists | Go module project |

Rules are evaluated in list order. All matching rules contribute their instructions (no exclusivity — a Python+uv project triggers both rules).

## CLI Behavior (`cli.py`)

Single command, no subcommands:

```
cc-project-init
```

### Flow

1. Resolve `project_root` = current working directory
2. Evaluate all rules against `project_root`, collect matches
3. If no rules match → print "No matching rules found for this project." and exit
4. Concatenate matched instructions into a sentinel-wrapped block
5. Read existing `CLAUDE.md` (create if missing)
6. **Idempotency check**: regex search for `<!-- USER INSTRUCTIONS START -->` ... `<!-- USER INSTRUCTIONS END -->` block
   - If found → replace the entire block (including sentinels) with updated content
   - If not found → append the block to the end of the file
7. **Preview**: Print the content that will be written, clearly labeled
8. **Confirm**: `typer.confirm("Apply these changes to CLAUDE.md?")` — exit if declined
9. Write the updated `CLAUDE.md`

### Sentinel Format

```markdown
<!-- USER INSTRUCTIONS START -->
# Project Environment

## Package Manager: uv
- Use `uv run python` to invoke Python instead of bare `python`
- Use `uv add <package>` to add dependencies

## Language: Python
- Follow PEP conventions
<!-- USER INSTRUCTIONS END -->
```

The regex pattern for matching: `r"<!-- USER INSTRUCTIONS START -->.*?<!-- USER INSTRUCTIONS END -->"` with `re.DOTALL`.

### Idempotency

- First run: appends the sentinel block to CLAUDE.md
- Subsequent runs: replaces the existing sentinel block with freshly generated content
- Content outside the sentinel block is never touched
- If project context changes (e.g., `uv.lock` is removed), re-running updates the block accordingly

## Dependencies

No new dependencies — uses only `typer` (already in project) and stdlib (`pathlib`, `re`).

## Out of Scope

- External config files for rules
- Dynamic template variables (Jinja2)
- Rule priority groups or conflict resolution
- Targeting CLAUDE.md in directories other than CWD
- Recursive project detection (monorepo sub-projects)
