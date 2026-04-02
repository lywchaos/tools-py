# llm-call: Batch File Processing

## Overview

Add a `--file` / `-f` option to the `llm-call` CLI that processes multiple words from a file concurrently. Words are removed from the file as they succeed; failed words remain for retry.

## CLI Interface

```
llm-call <word>                          # single word (existing)
llm-call --file words.txt                # batch from file
llm-call --file words.txt --concurrency 5  # batch with custom concurrency
```

- `prompt`: `Optional[str] = None` (was required positional)
- `--file` / `-f`: `Optional[Path] = None` — path to a file with one word per line
- `--concurrency` / `-c`: `int = 3` — max concurrent requests
- `prompt` and `--file` are mutually exclusive; exactly one must be provided

## Core Refactor

Extract an async function from the current `call` body:

```python
async def process_word(word: str, model: str, output_dir: Path) -> bool
```

- Handles the LLM call, file writing, and error output for a single word
- Returns `True` on success, `False` on failure
- Already-existing output files count as success (skip + return `True`)
- On API/network error: prints the error, returns `False` (does not exit)

The single-word path (`prompt` given) calls `process_word` directly.

## Batch Flow

1. Read lines from the file, strip whitespace, skip empty lines
2. Use `asyncio.Semaphore(concurrency)` to limit concurrent requests
3. Run all words concurrently via `asyncio.gather` with the semaphore
4. After each word succeeds: acquire a lock, rewrite the file with remaining words (thread-safe via asyncio lock)
5. After all words processed: if no words remain, delete the file
6. Print summary: `Processed N/M words. K failed.`

## Concurrency Detail

- Use `httpx.AsyncClient` instead of `httpx.post` for connection pooling
- `asyncio.Semaphore(concurrency)` gates the number of in-flight requests
- An `asyncio.Lock` protects file rewrites so concurrent completions don't race
- The file is rewritten after each individual success (crash-resilient)

## Error Handling

| Scenario | Behavior |
|---|---|
| `--file` and `prompt` both provided | Exit with error message |
| Neither provided | Exit with error message |
| File not found / unreadable | Exit with error |
| Individual word API failure | Log error, keep word in file, continue |
| Individual word network error | Log error, keep word in file, continue |
| Output file already exists | Skip (count as success), remove from file |

## File Format

Input file (`words.txt`):
```
error out
redact
latitude
```

- One word/phrase per line
- Empty lines and whitespace-only lines are ignored
- Leading/trailing whitespace is stripped

## Changes Summary

- **Modified file:** `src/tools_py/llm_call/cli.py`
- **No new files** — all changes are within the existing module
- **No new dependencies** — `asyncio` is stdlib; `httpx.AsyncClient` is already available from `httpx`
