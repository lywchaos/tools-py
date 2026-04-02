# llm-call Batch File Processing — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `--file` / `-f` and `--concurrency` / `-c` options to `llm-call` so it can process a batch of words concurrently from a file, removing each word on success.

**Architecture:** Extract the LLM call logic into an async `process_word` helper. The batch path reads words from a file, dispatches them concurrently with `asyncio.Semaphore`, and rewrites the file (under `asyncio.Lock`) after each success. The single-word path wraps the same helper in `asyncio.run`.

**Tech Stack:** Python 3.12+, typer, httpx (AsyncClient), asyncio, pytest + monkeypatch + tmp_path

**Spec:** `docs/superpowers/specs/2026-04-02-llm-call-batch-file-design.md`

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `src/tools_py/llm_call/cli.py` | Modify | CLI entry point, `process_word`, batch orchestration |
| `tests/llm_call/test_cli.py` | Create | All tests for single-word and batch modes |

---

### Task 1: Extract `process_word` async helper + single-word path

Refactor the existing `call` command so all LLM/file logic lives in an async function. The single-word CLI path calls it via `asyncio.run`. No new features yet — just the refactor.

**Files:**
- Modify: `src/tools_py/llm_call/cli.py`
- Create: `tests/llm_call/test_cli.py`

- [ ] **Step 1: Write tests for `process_word` (success + skip-existing + API error)**

Create `tests/llm_call/__init__.py` (empty) and `tests/llm_call/test_cli.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/llm_call/test_cli.py -v
```

Expected: FAIL — `process_word` does not exist yet.

- [ ] **Step 3: Implement `process_word` and refactor `call`**

Rewrite `src/tools_py/llm_call/cli.py` to:

```python
"""
llm_call.py - Call an LLM API and write the response to a file.

Uses the OpenAI-compatible chat completions endpoint.
"""

import asyncio
import os
from pathlib import Path

import httpx
import typer

app = typer.Typer(help="Call an LLM API and write the response to a file")

# ── Fill these in ──────────────────────────────────────────────
API_BASE = os.getenv("MODEL_PROXY_API_BASE")
API_KEY = os.getenv("MODEL_PROXY_API_KEY")
SYSTEM_PROMPT = """
你是一位拥有深厚语言学背景的英语专家。请针对用户给出的单词或词组，按以下结构提供精炼且深刻的解析：

基础信息：音标（美式）、核心义项（中英文对照）。

词源解构 (Etymology)：分析词根（Root）、前缀（Prefix）、后缀（Suffix），并简述词源演变逻辑。

地道例句：提供不少于 3 个不同场景的例句，附带中文翻译。

近义辨析 (Nuance)：列举 2-3 个近义词，并重点说明它们在语境、语体（正式/非正式）或程度上的细微差别。

延伸思考：从文化背景、常见搭配陷阱或逻辑联想的角度，给出一个有启发性的点。

要求：使用 Markdown 格式，运用标题、加粗和列表，确保视觉清晰。
""".strip()
# ───────────────────────────────────────────────────────────────


async def process_word(
    word: str, model: str, output_dir: Path, client: httpx.AsyncClient | None = None
) -> bool:
    """Process a single word: call LLM, write output file.

    Returns True on success (including skip-existing), False on failure.
    """
    output_file = output_dir / f"{word}.md"
    if output_file.exists():
        typer.echo(f"Skipped: {output_file} already exists.")
        return True

    messages = []
    if SYSTEM_PROMPT:
        messages.append({"role": "system", "content": SYSTEM_PROMPT})
    messages.append({"role": "user", "content": word})

    url = f"{API_BASE.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {"model": model, "messages": messages}

    async def _post(c: httpx.AsyncClient) -> bool:
        try:
            resp = await c.post(url, headers=headers, json=payload, timeout=120)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            typer.echo(
                f"Error [{word}]: API returned {e.response.status_code}: {e.response.text}",
                err=True,
            )
            return False
        except httpx.RequestError as e:
            typer.echo(f"Error [{word}]: Request failed: {e}", err=True)
            return False

        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file.write_text(f"#fsrs #english\n{content}", encoding="utf-8")
        typer.echo(f"Written to {output_file}")
        return True

    if client is not None:
        return await _post(client)

    async with httpx.AsyncClient() as c:
        return await _post(c)


@app.command()
def call(
    prompt: str = typer.Argument(..., help="User prompt to send to the LLM"),
    model: str = typer.Option("gpt-4o", "--model", "-m", help="Model name to use"),
):
    """Send a prompt to the LLM and write the response to a file."""
    if not API_BASE:
        typer.echo("Error: MODEL_PROXY_API_BASE is not set.", err=True)
        raise typer.Exit(code=1)
    if not API_KEY:
        typer.echo("Error: MODEL_PROXY_API_KEY is not set.", err=True)
        raise typer.Exit(code=1)

    vault_path = os.getenv("OBSIDIAN_VAULT_PATH")
    if not vault_path:
        typer.echo("Error: OBSIDIAN_VAULT_PATH is not set.", err=True)
        raise typer.Exit(code=1)

    output_dir = Path(vault_path) / "EnglishWords"
    ok = asyncio.run(process_word(prompt, model, output_dir))
    if not ok:
        raise typer.Exit(code=1)


def main():
    app()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/llm_call/test_cli.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/llm_call/__init__.py tests/llm_call/test_cli.py src/tools_py/llm_call/cli.py
git commit -m "refactor(llm-call): extract async process_word helper"
```

---

### Task 2: Add `--file` and `--concurrency` options with batch processing

Add the batch path: read words from a file, process concurrently with semaphore, rewrite file after each success under a lock, delete file when empty, print summary.

**Files:**
- Modify: `src/tools_py/llm_call/cli.py`
- Modify: `tests/llm_call/test_cli.py`

- [ ] **Step 1: Write tests for batch processing**

Append to `tests/llm_call/test_cli.py`:

```python
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

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/llm_call/test_cli.py::TestBatchProcessing -v
```

Expected: FAIL — `--file` option does not exist yet.

- [ ] **Step 3: Implement batch processing in `call` command**

Replace the `call` command in `src/tools_py/llm_call/cli.py` with:

```python
@app.command()
def call(
    prompt: str = typer.Argument(None, help="User prompt to send to the LLM"),
    file: Path = typer.Option(None, "--file", "-f", help="File with one word per line"),
    model: str = typer.Option("gpt-4o", "--model", "-m", help="Model name to use"),
    concurrency: int = typer.Option(3, "--concurrency", "-c", help="Max concurrent requests"),
):
    """Send a prompt to the LLM and write the response to a file."""
    if prompt and file:
        typer.echo("Error: Cannot use both a prompt argument and --file.", err=True)
        raise typer.Exit(code=1)
    if not prompt and not file:
        typer.echo("Error: Provide either a prompt argument or --file.", err=True)
        raise typer.Exit(code=1)

    if not API_BASE:
        typer.echo("Error: MODEL_PROXY_API_BASE is not set.", err=True)
        raise typer.Exit(code=1)
    if not API_KEY:
        typer.echo("Error: MODEL_PROXY_API_KEY is not set.", err=True)
        raise typer.Exit(code=1)

    vault_path = os.getenv("OBSIDIAN_VAULT_PATH")
    if not vault_path:
        typer.echo("Error: OBSIDIAN_VAULT_PATH is not set.", err=True)
        raise typer.Exit(code=1)

    output_dir = Path(vault_path) / "EnglishWords"

    if prompt:
        ok = asyncio.run(process_word(prompt, model, output_dir))
        if not ok:
            raise typer.Exit(code=1)
        return

    # -- Batch mode --
    if not file.exists():
        typer.echo(f"Error: File not found: {file}", err=True)
        raise typer.Exit(code=1)

    words = [w for line in file.read_text().splitlines() if (w := line.strip())]
    if not words:
        typer.echo("No words found in file.")
        return

    asyncio.run(_batch(words, model, output_dir, file, concurrency))


async def _batch(
    words: list[str], model: str, output_dir: Path, file: Path, concurrency: int
) -> None:
    sem = asyncio.Semaphore(concurrency)
    lock = asyncio.Lock()
    remaining: set[str] = set(words)

    async def _run(word: str, client: httpx.AsyncClient) -> bool:
        async with sem:
            ok = await process_word(word, model, output_dir, client=client)
        if ok:
            async with lock:
                remaining.discard(word)
                if remaining:
                    file.write_text("\n".join(remaining) + "\n")
                elif file.exists():
                    file.unlink()
        return ok

    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(*[_run(w, client) for w in words])

    success = sum(1 for r in results if r)
    total = len(words)
    failed = total - success
    typer.echo(f"Processed {success}/{total} words. {failed} failed.")
```

- [ ] **Step 4: Run all tests to verify they pass**

```bash
pytest tests/llm_call/test_cli.py -v
```

Expected: All tests PASS (TestProcessWord + TestBatchProcessing).

- [ ] **Step 5: Commit**

```bash
git add src/tools_py/llm_call/cli.py tests/llm_call/test_cli.py
git commit -m "feat(llm-call): add --file and --concurrency for batch processing"
```

---

### Task 3: Manual smoke test

Verify the CLI works end-to-end with real invocations.

- [ ] **Step 1: Test help output**

```bash
llm-call --help
```

Expected: Shows `prompt` argument as optional, `--file`, `--concurrency`, `--model` options.

- [ ] **Step 2: Test mutual exclusion error**

```bash
llm-call hello --file words.txt
```

Expected: `Error: Cannot use both a prompt argument and --file.`

- [ ] **Step 3: Test no-args error**

```bash
llm-call
```

Expected: `Error: Provide either a prompt argument or --file.`

- [ ] **Step 4: Test batch with real file (optional, requires API keys)**

```bash
llm-call --file words.txt --concurrency 2
```

Expected: Processes words, removes successes from file, prints summary.
