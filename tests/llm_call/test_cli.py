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
