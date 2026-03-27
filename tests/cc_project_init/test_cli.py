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
