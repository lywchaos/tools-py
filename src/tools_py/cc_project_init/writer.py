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
