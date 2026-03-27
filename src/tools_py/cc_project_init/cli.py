from pathlib import Path

import typer

from tools_py.cc_project_init.rules import detect_rules
from tools_py.cc_project_init.writer import build_block, update_claude_md

app = typer.Typer(help="Detect project context and generate CLAUDE.md instructions")


@app.callback(invoke_without_command=True)
def init():
    """Detect project context and update CLAUDE.md with environment instructions."""
    project_root = Path.cwd()
    claude_md_path = project_root / "CLAUDE.md"

    matched = detect_rules(project_root)
    if not matched:
        typer.echo("No matching rules found for this project.")
        return

    typer.echo(f"Detected: {', '.join(r.name for r in matched)}\n")

    block = build_block([r.instructions for r in matched])
    new_content = update_claude_md(claude_md_path, block)

    typer.echo("--- Preview ---")
    typer.echo(block)
    typer.echo("--- End Preview ---\n")

    if not typer.confirm("Apply these changes to CLAUDE.md?"):
        typer.echo("Aborted.")
        raise typer.Exit()

    claude_md_path.write_text(new_content)
    typer.echo(f"Updated {claude_md_path}")


def main():
    app()


if __name__ == "__main__":
    main()
