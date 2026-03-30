# tmux-claude-dash Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a bash+fzf tmux popup dashboard that lists all panes running `claude` and navigates to the selected one.

**Architecture:** Single self-contained bash script. Discovers claude processes by scanning the process tree of each tmux pane, displays matches in fzf with pane content preview, and navigates via tmux switch-client or select-window/select-pane depending on session context.

**Tech Stack:** Bash, fzf, tmux, ps, pgrep

---

### Task 1: Create the script skeleton with dependency checks

**Files:**
- Create: `bin/tmux-claude-dash`

- [ ] **Step 1: Create the bin directory and script file**

```bash
mkdir -p bin
```

- [ ] **Step 2: Write the script skeleton**

Write `bin/tmux-claude-dash`:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Check dependencies
for cmd in tmux fzf pgrep; do
  if ! command -v "$cmd" &>/dev/null; then
    echo "Error: $cmd is required but not installed." >&2
    exit 1
  fi
done
```

- [ ] **Step 3: Make it executable and verify**

```bash
chmod +x bin/tmux-claude-dash
./bin/tmux-claude-dash
```

Expected: exits cleanly with no output (all deps present), or prints an error if a dep is missing.

- [ ] **Step 4: Commit**

```bash
git add bin/tmux-claude-dash
git commit -m "feat(tmux-claude-dash): add script skeleton with dependency checks"
```

---

### Task 2: Implement claude process discovery

**Files:**
- Modify: `bin/tmux-claude-dash`

- [ ] **Step 1: Add the discovery function**

Append to `bin/tmux-claude-dash` after the dependency checks:

```bash
# Walk process tree to find a process named "claude" under a given PID.
# Returns 0 if found, 1 otherwise.
has_claude_child() {
  local pid=$1 depth=${2:-0}
  (( depth > 5 )) && return 1

  local children
  children=$(pgrep -P "$pid" 2>/dev/null) || return 1

  local child
  for child in $children; do
    local comm
    comm=$(ps -p "$child" -o comm= 2>/dev/null) || continue
    if [[ "$comm" == "claude" ]]; then
      return 0
    fi
    if has_claude_child "$child" $((depth + 1)); then
      return 0
    fi
  done
  return 1
}

# Collect all tmux panes running claude.
# Output format: target<TAB>command<TAB>cwd
discover_claude_panes() {
  local found=0
  while IFS=' ' read -r target pane_pid cwd; do
    if has_claude_child "$pane_pid"; then
      # Shorten home directory to ~
      cwd="${cwd/#$HOME/~}"
      printf '%s\t%s\t%s\n' "$target" "claude" "$cwd"
      found=1
    fi
  done < <(tmux list-panes -a -F '#{session_name}:#{window_index}.#{pane_index} #{pane_pid} #{pane_current_path}')

  if (( found == 0 )); then
    echo "No Claude sessions found." >&2
    exit 0
  fi
}
```

- [ ] **Step 2: Add a test invocation and verify**

Temporarily add this at the end of the script to test discovery:

```bash
discover_claude_panes
```

Run inside tmux (where a claude process is running):

```bash
./bin/tmux-claude-dash
```

Expected: tab-separated lines like `tools-py:0.1	claude	~/workspace/tools-py`. If no claude processes are running, prints "No Claude sessions found." to stderr.

- [ ] **Step 3: Commit**

```bash
git add bin/tmux-claude-dash
git commit -m "feat(tmux-claude-dash): add claude process discovery"
```

---

### Task 3: Add fzf display with preview

**Files:**
- Modify: `bin/tmux-claude-dash`

- [ ] **Step 1: Replace the test invocation with fzf piping**

Remove the temporary `discover_claude_panes` call at the end. Replace with:

```bash
# Main
selection=$(
  discover_claude_panes | \
  column -t -s $'\t' | \
  fzf \
    --ansi \
    --no-sort \
    --reverse \
    --header="Claude Sessions (enter: switch, esc: cancel)" \
    --preview='tmux capture-pane -p -t {1}' \
    --preview-window=right:60%
) || exit 0
```

The `column -t` aligns columns. `{1}` in the preview command extracts the first whitespace-delimited field (the target). `|| exit 0` handles the case where the user presses Esc (fzf returns non-zero).

- [ ] **Step 2: Verify inside tmux**

```bash
tmux display-popup -E -w 80% -h 60% "$PWD/bin/tmux-claude-dash"
```

Expected: a popup with aligned columns, a header, and a preview pane showing the captured content of the highlighted pane. Pressing Esc closes cleanly.

- [ ] **Step 3: Commit**

```bash
git add bin/tmux-claude-dash
git commit -m "feat(tmux-claude-dash): add fzf display with pane preview"
```

---

### Task 4: Add navigation logic

**Files:**
- Modify: `bin/tmux-claude-dash`

- [ ] **Step 1: Add navigation after fzf selection**

Append after the `selection=...` block:

```bash
# Extract target (first field)
target=$(echo "$selection" | awk '{print $1}')
target_session="${target%%:*}"

current_session=$(tmux display-message -p '#S')

if [[ "$target_session" == "$current_session" ]]; then
  tmux select-window -t "$target"
  tmux select-pane -t "$target"
else
  tmux switch-client -t "$target"
fi
```

- [ ] **Step 2: Verify end-to-end inside tmux**

Test both cases:

1. **Same session**: open the popup from a session that has a claude pane, select it. Expected: switches to that window/pane within the same session.
2. **Cross session**: open the popup from a different session, select a claude pane in another session. Expected: switches the client to the target session/window/pane.

```bash
tmux display-popup -E -w 80% -h 60% "$PWD/bin/tmux-claude-dash"
```

- [ ] **Step 3: Commit**

```bash
git add bin/tmux-claude-dash
git commit -m "feat(tmux-claude-dash): add same/cross-session navigation"
```

---

### Task 5: Final polish and documentation

**Files:**
- Modify: `bin/tmux-claude-dash` (add usage comment at top)

- [ ] **Step 1: Add a usage comment to the script**

Add after the shebang line:

```bash
# tmux-claude-dash — fzf-powered dashboard for navigating tmux panes running Claude
#
# Usage:
#   tmux display-popup -E -w 80% -h 60% "/path/to/tmux-claude-dash"
#
# Bind to a key in .tmux.conf:
#   bind C-c display-popup -E -w 80% -h 60% "/path/to/tmux-claude-dash"
```

- [ ] **Step 2: Full end-to-end test**

Run the complete flow:

```bash
tmux display-popup -E -w 80% -h 60% "$PWD/bin/tmux-claude-dash"
```

Verify:
- Columns are aligned
- Preview shows pane content
- Same-session navigation works
- Cross-session navigation works
- Esc cancels cleanly
- No claude processes shows the empty message

- [ ] **Step 3: Commit**

```bash
git add bin/tmux-claude-dash
git commit -m "feat(tmux-claude-dash): add usage documentation"
```
