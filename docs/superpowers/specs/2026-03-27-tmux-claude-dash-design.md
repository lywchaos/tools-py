# tmux-claude-dash

A single bash script that shows an fzf-powered tmux popup listing all panes running `claude`, with instant navigation to any selected pane.

## Dependencies

- `tmux` (obviously)
- `fzf` (interactive filtering and preview)
- Standard POSIX utilities: `ps`, `pgrep`, `awk`, `printf`

## Discovery

For each tmux pane:

1. Query all panes via `tmux list-panes -a -F "#{session_name}:#{window_index}.#{pane_index} #{pane_pid} #{pane_current_path}"`
2. For each pane PID, walk the process tree (children of the shell PID) to find any process whose command is `claude`
3. Collect matching panes with:
   - **Target**: `session_name:window_index.pane_index`
   - **Command**: the `claude` command line from `ps`
   - **CWD**: `pane_current_path` (the pane's working directory)

Process tree walking uses `pgrep -P <pid>` recursively (or a single `ps -e -o ppid,pid,comm` scan for efficiency).

## Display

Pipe discovered entries into `fzf` with:

- **Columnar layout**: aligned columns via `printf` formatting — target, command, cwd
- **Header**: `"Claude Sessions"` or similar
- **Preview**: `tmux capture-pane -p -t <target>` showing a snapshot of the pane content
- **Options**: `--ansi --no-sort --reverse` for a clean look
- **Empty state**: if no claude processes found, print a message and exit

Example row:
```
tools-py:0.1          claude          ~/workspace/tools-py
english:0.1           claude          ~/workspace/english
```

## Navigation

On fzf selection:

1. Extract `session:window.pane` from the selected line
2. Determine current session via `tmux display-message -p '#S'`
3. Route:
   - **Same session**: `tmux select-window -t <target> && tmux select-pane -t <target>`
   - **Different session**: `tmux switch-client -t <target>`

## Invocation

The script is invoked via `tmux display-popup`. Users bind it to a key in `.tmux.conf`:

```tmux
bind C-c display-popup -E -w 80% -h 60% "/path/to/tmux-claude-dash"
```

The `-E` flag ensures the popup closes when the script exits (i.e., after fzf selection or cancellation).

## File

Single file: `bin/tmux-claude-dash` — a self-contained bash script, executable, with a shebang line.

## Edge Cases

- **No claude processes**: print "No Claude sessions found" and exit 0
- **Single match**: still show fzf (user might want to preview before switching, or cancel)
- **Pane PID has deeply nested children**: walk up to 5 levels deep (covers shell → node/python → claude chains)
- **CWD display**: shorten home directory prefix to `~` for readability
