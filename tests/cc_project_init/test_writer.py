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
