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
