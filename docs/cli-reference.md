# CLI Command Reference

This document covers all available CLI commands in WorktreeForge.

## Global Options

- `--help`: Show command documentation and exit.
- `--version`: Show package version.

---

## Worktree Commands

### `worktreeforge list`
Display an overview of all active worktrees for the current repository.

```bash
worktreeforge list
```

Columns returned:
- `Path`: Absolute or relative path to the worktree folder.
- `Branch`: Checked-out branch or commit hash.
- `Status`: Clean, Dirty, or Locked.
- `Ports`: Allocated port variables and their numbers.
- `PR Status`: GitHub Pull Request state (OPEN, MERGED, CLOSED, or NONE).

---

### `worktreeforge new <branch>`
Provision a new Git worktree and configure port offsets automatically.

```bash
worktreeforge new feature/payments
worktreeforge new bugfix/auth --base origin/main
worktreeforge new experimental/cache --path ../custom-dir --port-offset 5
```

Options:
- `<branch>`: Branch name to checkout or create.
- `--base <ref>`: Base commit, tag, or branch to fork from (default: `HEAD`).
- `--path <dir>`: Custom destination folder path (default: `../{repo}-{branch}`).
- `--port-offset <int>`: Explicit port offset increment.
- `--no-ports`: Skip port multiplexing and `.env.local` generation.
- `--link-deps`: Fast-link dependency folders (`node_modules`, `.venv`, `.cargo`, `target`) from the root workspace using directory junctions or symlinks.
- `--open`: Open the created worktree in your configured editor (VS Code, Cursor).

---

### `worktreeforge remove <name_or_path>`
Remove a worktree directory and prune Git references.

```bash
worktreeforge remove feature/payments
worktreeforge remove ../repo-payments --force
```

Options:
- `--force`: Force removal even if uncommitted or untracked changes exist.
- `--delete-branch`: Also delete the associated local Git branch after removal.

---

### `worktreeforge lock <name_or_path>`
Lock a worktree to prevent it from being pruned or removed accidentally.

```bash
worktreeforge lock feature/critical-hotfix --reason "Active client benchmark"
```

---

### `worktreeforge unlock <name_or_path>`
Unlock a locked worktree.

```bash
worktreeforge unlock feature/critical-hotfix
```

---

### `worktreeforge prune`
Clean up orphaned worktree records and optionally remove merged branches.

```bash
worktreeforge prune
worktreeforge prune --merged
```

Options:
- `--merged`: Automatically identify and delete worktrees whose GitHub PRs are merged.
- `--dry-run`: Output what would be removed without touching disk or Git records.

---

## Port Multiplexer Commands

### `worktreeforge ports`
Display active port reservations and check TCP socket availability.

```bash
worktreeforge ports
worktreeforge ports --release feature/payments
```

---

## Stash Studio Commands

### `worktreeforge stash list`
List all stashes in the current repository with date, author, and branch origin.

```bash
worktreeforge stash list
```

---

### `worktreeforge stash show <id>`
Display file list and unified diff for a specific stash index (e.g. `0` or `stash@{0}`).

```bash
worktreeforge stash show 0
```

---

### `worktreeforge stash search <query>`
Search stash messages, file names, and diff contents for a query string.

```bash
worktreeforge stash search "stripe"
```

---

### `worktreeforge stash apply <id>`
Apply stash changes to the current working directory.

```bash
worktreeforge stash apply 0
```

---

### `worktreeforge stash pop <id>`
Apply stash changes and drop the entry from the stash stack.

```bash
worktreeforge stash pop 0
```

---

### `worktreeforge stash drop <id>`
Drop a stash entry permanently.

```bash
worktreeforge stash drop 0
```

---

## Dashboard Commands

### `worktreeforge tui`
Launch the interactive terminal user interface powered by Textual.

```bash
worktreeforge tui
```

---

### `worktreeforge web`
Start the FastAPI web studio server and browser dashboard.

```bash
worktreeforge web --port 8990 --host 127.0.0.1
```

---

## Process & Dev Server Supervisor

### `worktreeforge start <name_or_path> [command]`
Start a dev server or build command in the background inside the target worktree. If command is omitted, it auto-detects `npm run dev`, `pnpm dev`, `cargo run`, or `python main.py`.

```bash
worktreeforge start feature/payments
worktreeforge start feature/payments "npm run start"
```

---

### `worktreeforge stop <name_or_path>`
Terminate the running background process and its entire child process tree.

```bash
worktreeforge stop feature/payments
```

---

### `worktreeforge logs <name_or_path>`
Inspect live or buffered stdout and stderr logs for the background process.

```bash
worktreeforge logs feature/payments
worktreeforge logs feature/payments --lines 50
```

---

## Comparison Studio

### `worktreeforge compare [target_branch] [base_branch]`
Compare commit divergence, ahead/behind counts, commit logs, and file diffs between two branches or worktrees. Defaults to comparing current branch against the default branch (`main` or `master`).

```bash
worktreeforge compare
worktreeforge compare feature/payments main
```

---

## Navigation & Launcher

### `worktreeforge open <name_or_path>`
Open the worktree in your code editor or probe and launch its running web application in the default browser.

```bash
worktreeforge open feature/payments --editor
worktreeforge open feature/payments --browser
```

---

### `worktreeforge path <name_or_path>`
Print the exact absolute filesystem path of a worktree (used for script piping and terminal cd).

```bash
worktreeforge path feature/payments
```

---

### `worktreeforge init [pwsh|bash]`
Print shell integration script defining the fast cd wrapper `wtf cd <branch>`:

```powershell
# PowerShell ($PROFILE):
Invoke-Expression (& worktreeforge init pwsh)
```

```bash
# Bash / Zsh (~/.bashrc or ~/.zshrc):
eval "$(worktreeforge init bash)"
```

---

## GitHub Pull Requests

### `worktreeforge pr create [branch]`
Create a GitHub Pull Request for the worktree branch using the `gh` CLI.

```bash
worktreeforge pr create
worktreeforge pr create feature/payments --title "Add Stripe webhook listener" --draft
```
