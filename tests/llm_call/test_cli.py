import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest


# Helper to build a fake successful httpx.Response
def _ok_response(content: str = "mock response") -> httpx.Response:
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": content}}]},
        request=httpx.Request("POST", "https://fake/chat/completions"),
    )


def _error_response(status: int = 500, text: str = "fail") -> httpx.Response:
    return httpx.Response(
        status,
        text=text,
        request=httpx.Request("POST", "https://fake/chat/completions"),
    )


@pytest.fixture()
def env(monkeypatch):
    monkeypatch.setenv("MODEL_PROXY_API_BASE", "https://fake")
    monkeypatch.setenv("MODEL_PROXY_API_KEY", "key")


class TestProcessWord:
    def test_success_writes_file(self, tmp_path: Path, env):
        from tools_py.llm_call.cli import process_word

        with patch("tools_py.llm_call.cli.httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value.__aenter__ = AsyncMock(return_value=MockClient.return_value)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value.post = AsyncMock(return_value=_ok_response("hello"))

            result = asyncio.run(process_word("testword", "gpt-4o", tmp_path))

        assert result is True
        out = tmp_path / "testword.md"
        assert out.exists()
        assert out.read_text() == "#fsrs #english\nhello"

    def test_skip_existing(self, tmp_path: Path, env):
        from tools_py.llm_call.cli import process_word

        (tmp_path / "testword.md").write_text("already here")
        result = asyncio.run(process_word("testword", "gpt-4o", tmp_path))
        assert result is True  # counts as success

    def test_api_error_returns_false(self, tmp_path: Path, env):
        from tools_py.llm_call.cli import process_word

        with patch("tools_py.llm_call.cli.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=MockClient.return_value)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            resp = _error_response(500, "server error")
            MockClient.return_value.post = AsyncMock(side_effect=httpx.HTTPStatusError("fail", request=resp.request, response=resp))

            result = asyncio.run(process_word("testword", "gpt-4o", tmp_path))

        assert result is False
        assert not (tmp_path / "testword.md").exists()


class TestBatchProcessing:
    def test_batch_removes_successful_words(self, tmp_path: Path, env, monkeypatch):
        from tools_py.llm_call.cli import app

        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
        words_file = tmp_path / "words.txt"
        words_file.write_text("alpha\nbeta\n")
        output_dir = tmp_path / "EnglishWords"
        output_dir.mkdir()

        with patch("tools_py.llm_call.cli.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            MockClient.return_value.__aenter__ = AsyncMock(return_value=instance)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            instance.post = AsyncMock(return_value=_ok_response("content"))

            from typer.testing import CliRunner
            runner = CliRunner()
            result = runner.invoke(app, ["--file", str(words_file)])

        assert result.exit_code == 0
        assert "2/2" in result.output
        # file should be deleted when empty
        assert not words_file.exists()

    def test_batch_keeps_failed_words(self, tmp_path: Path, env, monkeypatch):
        from tools_py.llm_call.cli import app

        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
        words_file = tmp_path / "words.txt"
        words_file.write_text("good\nbad\n")
        output_dir = tmp_path / "EnglishWords"
        output_dir.mkdir()

        async def mock_post(*args, **kwargs):
            payload = kwargs.get("json", {})
            word = payload["messages"][-1]["content"]
            if word == "bad":
                raise httpx.RequestError("network down")
            return _ok_response("content")

        with patch("tools_py.llm_call.cli.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            MockClient.return_value.__aenter__ = AsyncMock(return_value=instance)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            instance.post = AsyncMock(side_effect=mock_post)

            from typer.testing import CliRunner
            runner = CliRunner()
            result = runner.invoke(app, ["--file", str(words_file)])

        assert result.exit_code == 0
        assert "1/2" in result.output
        remaining = words_file.read_text().strip().splitlines()
        assert remaining == ["bad"]

    def test_batch_skips_empty_lines(self, tmp_path: Path, env, monkeypatch):
        from tools_py.llm_call.cli import app

        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
        words_file = tmp_path / "words.txt"
        words_file.write_text("\n  \nword\n\n")
        output_dir = tmp_path / "EnglishWords"
        output_dir.mkdir()

        with patch("tools_py.llm_call.cli.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            MockClient.return_value.__aenter__ = AsyncMock(return_value=instance)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            instance.post = AsyncMock(return_value=_ok_response("content"))

            from typer.testing import CliRunner
            runner = CliRunner()
            result = runner.invoke(app, ["--file", str(words_file)])

        assert result.exit_code == 0
        assert "1/1" in result.output

    def test_mutual_exclusion(self, tmp_path: Path, env, monkeypatch):
        from tools_py.llm_call.cli import app

        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
        words_file = tmp_path / "words.txt"
        words_file.write_text("word\n")

        from typer.testing import CliRunner
        runner = CliRunner()
        result = runner.invoke(app, ["hello", "--file", str(words_file)])
        assert result.exit_code == 1
        assert "Cannot use both" in result.output

    def test_no_prompt_no_file(self, env, monkeypatch):
        from tools_py.llm_call.cli import app

        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", "/tmp")

        from typer.testing import CliRunner
        runner = CliRunner()
        result = runner.invoke(app, [])
        assert result.exit_code == 1
