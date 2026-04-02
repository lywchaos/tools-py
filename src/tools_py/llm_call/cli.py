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


def main():
    app()


if __name__ == "__main__":
    main()
