"""
linky.py - Symlink-based file synchronization tool

Manages git-ignored files by copying them to a separate repository and
replacing originals with symlinks.
"""

import fnmatch
import shutil
import subprocess
from pathlib import Path

import typer

app = typer.Typer(help="Symlink-based file synchronization tool")


def discover_gitignored_files(patterns: list[str]) -> list[Path]:
    """Discover git-ignored files matching glob patterns."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "-oi", "--exclude-standard"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        typer.echo(f"Error: Failed to run git ls-files: {e.stderr}", err=True)
        raise typer.Exit(code=1)
    except FileNotFoundError:
        typer.echo("Error: git command not found", err=True)
        raise typer.Exit(code=1)

    files = result.stdout.strip().split("\n") if result.stdout.strip() else []
    matched = []
    for f in files:
        path = Path(f)
        for pattern in patterns:
            if fnmatch.fnmatch(path.name, pattern):
                matched.append(path)
                break
    return matched


def get_real_content_path(path: Path) -> Path:
    """If path is a symlink, resolve to get the actual file."""
    if path.is_symlink():
        return path.resolve()
    return path


def prompt_overwrite(filepath: str) -> str:
    """Prompt user for overwrite decision. Returns 'y', 'n', or 'a'."""
    while True:
        response = typer.prompt(f"File exists: {filepath}\nOverwrite? [y]es / [n]o / [a]ll").lower().strip()
        if response in ("y", "yes"):
            return "y"
        elif response in ("n", "no"):
            return "n"
        elif response in ("a", "all"):
            return "a"
        typer.echo("Please enter 'y', 'n', or 'a'")


@app.command("store")
def cmd_store(
    source_path: str = typer.Option(..., "--source-path", help="Destination path where files will be copied"),
    patterns: str = typer.Option(..., "--patterns", help="Comma-separated glob patterns (e.g., '*.env,CLAUDE.md')"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be done without making changes"),
):
    """Copy git-ignored files to source path and replace with symlinks."""
    source_path_resolved = Path(source_path).resolve()
    patterns_list = [p.strip() for p in patterns.split(",")]

    # Discover files
    files = discover_gitignored_files(patterns_list)
    if not files:
        typer.echo("No git-ignored files found matching the patterns.")
        return

    # Plan operations
    operations = []
    for f in files:
        src = Path(f)
        dest = source_path_resolved / f
        operations.append((src, dest))

    # Show summary
    typer.echo("\n=== Store Summary ===")
    typer.echo(f"Source path: {source_path_resolved}")
    typer.echo(f"Patterns: {patterns_list}")
    typer.echo(f"\nFiles to process ({len(operations)}):")
    for src, dest in operations:
        typer.echo(f"  {src} -> {dest}")
        typer.echo(f"    (then symlink {src} -> {dest})")

    if dry_run:
        typer.echo("\n[DRY RUN] No changes made.")
        return

    # Confirm
    if not typer.confirm("\nProceed with store?"):
        typer.echo("Aborted.")
        return

    # Execute
    overwrite_all = False
    for src, dest in operations:
        try:
            # Check if destination exists
            if dest.exists() and not overwrite_all:
                choice = prompt_overwrite(str(dest))
                if choice == "n":
                    typer.echo(f"  Skipped: {src}")
                    continue
                elif choice == "a":
                    overwrite_all = True

            # Create destination directory
            dest.parent.mkdir(parents=True, exist_ok=True)

            # Get real content (follow symlinks)
            content_path = get_real_content_path(src)

            # Copy file content
            shutil.copy2(content_path, dest)
            typer.echo(f"  Copied: {src} -> {dest}")

            # Remove original (file or symlink)
            if src.is_symlink():
                src.unlink()
            else:
                src.unlink()

            # Create symlink
            src.symlink_to(dest)
            typer.echo(f"  Linked: {src} -> {dest}")

        except PermissionError as e:
            typer.echo(f"Error: Permission denied for {src}: {e}", err=True)
            raise typer.Exit(code=1)
        except OSError as e:
            typer.echo(f"Error: Failed to process {src}: {e}", err=True)
            raise typer.Exit(code=1)

    typer.echo("\nStore complete.")


@app.command("apply")
def cmd_apply(
    source_path: str = typer.Option(..., "--source-path", help="Path containing files to link"),
    target_path: str = typer.Option(..., "--target-path", help="Directory where symlinks will be created"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be done without making changes"),
):
    """Create symlinks from source path into target directory."""
    source_path_resolved = Path(source_path).resolve()
    target_path_resolved = Path(target_path).resolve()

    # Validate source path
    if not source_path_resolved.exists():
        typer.echo(f"Error: Source path does not exist: {source_path_resolved}", err=True)
        raise typer.Exit(code=1)

    if not source_path_resolved.is_dir():
        typer.echo(f"Error: Source path is not a directory: {source_path_resolved}", err=True)
        raise typer.Exit(code=1)

    # Collect all files in source
    files = list(source_path_resolved.rglob("*"))
    files = [f for f in files if f.is_file()]

    if not files:
        typer.echo(f"Error: Source path contains no files: {source_path_resolved}", err=True)
        raise typer.Exit(code=1)

    # Plan operations
    operations = []
    for src_file in files:
        rel_path = src_file.relative_to(source_path_resolved)
        target_file = target_path_resolved / rel_path
        operations.append((src_file, target_file))

    # Show summary
    typer.echo("\n=== Apply Summary ===")
    typer.echo(f"Source path: {source_path_resolved}")
    typer.echo(f"Target path: {target_path_resolved}")
    typer.echo(f"\nSymlinks to create ({len(operations)}):")
    for src_file, target_file in operations:
        typer.echo(f"  {target_file} -> {src_file}")

    if dry_run:
        typer.echo("\n[DRY RUN] No changes made.")
        return

    # Confirm
    if not typer.confirm("\nProceed with apply?"):
        typer.echo("Aborted.")
        return

    # Execute
    for src_file, target_file in operations:
        try:
            # Create target directory
            target_file.parent.mkdir(parents=True, exist_ok=True)

            # Remove existing file/symlink if present
            if target_file.exists() or target_file.is_symlink():
                target_file.unlink()
                typer.echo(f"  Removed existing: {target_file}")

            # Create symlink
            target_file.symlink_to(src_file)
            typer.echo(f"  Linked: {target_file} -> {src_file}")

        except PermissionError as e:
            typer.echo(f"Error: Permission denied for {target_file}: {e}", err=True)
            raise typer.Exit(code=1)
        except OSError as e:
            typer.echo(f"Error: Failed to create symlink {target_file}: {e}", err=True)
            raise typer.Exit(code=1)

    typer.echo("\nApply complete.")


def main():
    app()


if __name__ == "__main__":
    main()
