# WorktreeForge: Master Implementation Plan

> High-Speed Git Worktree Supervisor, Stash Studio & Local Port Multiplexer
>
> Eliminates friction when developing in parallel with Git Worktrees and AI assistants. Automatically allocates non-conflicting dev server ports (`PORT=3000`, `PORT=3001`...) via `.env.local`, provides an interactive Stash Studio, and enables safe cleanup of worktrees when associated GitHub pull requests are merged.

---

## 1. System Architecture

```
+-----------------------------------------------------------------------------------+
|                                  WORKTREEFORGE                                    |
+-----------------------------------------+-----------------------------------------+
                                          |
        +---------------------------------+---------------------------------+
        |                                                                   |
+-------v-------------------------+                 +-----------------------v-------+
|    Worktree Lifecycle Manager   |                 |    Local Port Multiplexer     |
|  * Fast Multi-Branch Checkout   |                 |  * .env / package.json Scan   |
|  * Directory Isolation          |                 |  * Dynamic Port Offsets       |
|  * Safe Dirty State Detection   |                 |  * Real TCP Socket Probing    |
|  * Lock / Unlock Protection     |                 |  * .worktreeforge.ports.json  |
+-------+-------------------------+                 +-----------------------+-------+
        |                                                                   |
        +---------------------------------+---------------------------------+
                                          |
                        +-----------------v-----------------+
                        |       Visual Stash Studio         |
                        |  * Searchable Stash Hierarchy     |
                        |  * Unified & Per-File Diff Viewer |
                        |  * Apply, Pop, Drop, Branch-Out   |
                        +-----------------+-----------------+
                                          |
                        +-----------------v-----------------+
                        |    GitHub PR Sync & Auto-Prune    |
                        |  * Merged PR Detection via gh CLI |
                        |  * Safe Unlink & Disk Reclamation |
                        |  * Interactive TUI & Web Studio   |
                        +-----------------------------------+
```

---

## 2. Directory Layout

```
worktreeforge/
├── pyproject.toml
├── requirements.txt
├── README.md
├── LICENSE
├── configs/
│   └── worktreeforge.default.yaml    # Port allocation ranges, base directories, hooks
├── docs/
│   ├── architecture.md
│   ├── cli-reference.md
│   ├── worktree-workflows.md
│   └── images/
│       ├── worktreeforge_preview.png
│       └── worktreeforge_demo.gif
├── src/
│   └── worktreeforge/
│       ├── __init__.py
│       ├── py.typed
│       ├── core/
│       │   ├── __init__.py
│       │   ├── config.py             # User preferences & workspace settings
│       │   ├── git_client.py         # Native Git CLI subprocess wrapper
│       │   ├── models.py             # Pydantic schemas (WorktreeInfo, StashInfo, PortMapping)
│       │   └── supervisor.py         # Worktree lifecycle coordinator & dirty state guard
│       ├── multiplexer/
│       │   ├── __init__.py
│       │   ├── port_allocator.py     # Port reservation table & socket availability prober
│       │   ├── env_patcher.py        # Updates .env, .env.local with allocated ports
│       │   └── port_scanner.py       # Scans .env, package.json, docker-compose, configs
│       ├── stash/
│       │   ├── __init__.py
│       │   └── inspector.py          # Parses git stash list, commits, unified diffs & search
│       ├── github/
│       │   ├── __init__.py
│       │   └── pr_checker.py         # Interrogates `gh pr view` for merged/closed branches
│       ├── tui/
│       │   ├── __init__.py
│       │   └── app.py                # Textual interactive terminal dashboard
│       ├── web/
│       │   ├── __init__.py
│       │   ├── server.py             # FastAPI backend with REST endpoints & WebSockets
│       │   └── static/
│       │       ├── index.html        # Modern responsive dark-mode dashboard
│       │       ├── app.js            # Real-time state synchronization & actions
│       │       └── style.css         # Clean engineering design system
│       └── cli/
│           ├── __init__.py
│           └── main.py               # Typer CLI with rich output formatting
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_git_client.py
    ├── test_supervisor.py
    ├── test_port_scanner.py
    ├── test_port_allocator.py
    ├── test_env_patcher.py
    ├── test_stash_inspector.py
    ├── test_github_pr_checker.py
    ├── test_cli.py
    └── test_web_server.py
```

---

## 3. Detailed Step-by-Step Task Breakdown

### Task 1: Domain Models & Configuration Engine
- [x] Subtask 1.1: Define Pydantic models in `src/worktreeforge/core/models.py`:
  - `WorktreeInfo`: path, commit_hash, branch, is_bare, is_locked, lock_reason, is_main, is_dirty, active_ports, pr_status.
  - `PortAllocation`: worktree_path, branch, port_variable, base_port, allocated_port, is_active.
  - `PortRegistry`: table of active allocations saved to `.worktreeforge.ports.json`.
  - `StashEntry`: index, id, hash, message, branch, date, author, files_changed, insertions, deletions.
  - `StashDiff`: stash_index, raw_diff, per_file_diffs.
  - `PRStatus`: state (`OPEN`, `MERGED`, `CLOSED`, `NONE`), number, url, title, merged_at.
- [x] Subtask 1.2: Implement `src/worktreeforge/core/config.py` loading YAML configuration hierarchy (defaults -> `~/.config/worktreeforge/config.yaml` -> `.worktreeforge.yaml`).

### Task 2: Git Native Subprocess Client
- [x] Subtask 2.1: Implement `src/worktreeforge/core/git_client.py`:
  - Execute `git` subprocesses with UTF-8 decoding and error handling.
  - `get_repo_root()`: detect repo root or raise informative error.
  - `list_worktrees()`: parse `git worktree list --porcelain` into `WorktreeInfo` records.
  - `add_worktree(path, branch, base_ref=None, new_branch=True)`: execute `git worktree add`.
  - `remove_worktree(path, force=False)`: execute `git worktree remove`.
  - `lock_worktree(path, reason=None)` and `unlock_worktree(path)`: execute `git worktree lock/unlock`.
  - `prune_worktrees()`: execute `git worktree prune`.
  - `check_dirty(path)`: run `git status --porcelain` to detect uncommitted/untracked changes.
  - `list_stashes()`: execute `git stash list` with format parsing.
  - `get_stash_diff(index)`: execute `git stash show -p stash@{index}`.
  - `apply_stash(index)`, `pop_stash(index)`, `drop_stash(index)`.

### Task 3: Port Multiplexing Engine
- [x] Subtask 3.1: Implement `src/worktreeforge/multiplexer/port_scanner.py`:
  - Scan `.env`, `.env.example`, `.env.local` for port variables (`PORT=...`, `SERVER_PORT=...`, `VITE_PORT=...`, etc.).
  - Scan `package.json` scripts for port arguments (e.g., `-p 3000`, `--port 3000`).
  - Scan `docker-compose.yml` or `pyproject.toml` for standard port definitions.
- [x] Subtask 3.2: Implement `src/worktreeforge/multiplexer/port_allocator.py`:
  - Socket verification: test candidate ports via TCP socket bind (`socket.socket(socket.AF_INET, socket.SOCK_STREAM)`).
  - Deterministic offset calculation based on worktree order or registry history.
  - Maintain `.worktreeforge.ports.json` in repository root for persistent allocation tracking.
  - Release allocations when a worktree is removed.
- [x] Subtask 3.3: Implement `src/worktreeforge/multiplexer/env_patcher.py`:
  - Write or update `.env.local` inside the worktree directory.
  - Maintain comments and existing overrides while injecting new allocated ports.

### Task 4: Stash Studio Engine
- [x] Subtask 4.1: Implement `src/worktreeforge/stash/inspector.py`:
  - Parse commit hashes, dates, branches, and messages from `git stash list`.
  - Parse unified diffs into structured file-by-file objects with added/deleted line statistics.
  - Search engine across stash summaries, touched file paths, and diff hunks.
  - Integration with Git client for applying, popping, and dropping stashes.

### Task 5: GitHub PR Synchronization & Safe Pruning
- [x] Subtask 5.1: Implement `src/worktreeforge/github/pr_checker.py`:
  - Interrogate GitHub CLI `gh pr view <branch> --json state,number,url,title,mergedAt`.
  - Graceful fallback when `gh` CLI is absent or repository has no GitHub remote.
  - Cache results with a short TTL to prevent redundant API queries.
- [x] Subtask 5.2: Implement `src/worktreeforge/core/supervisor.py`:
  - Orchestrate worktree creation: path calculation, branch creation, git worktree add, port allocation, .env.local patching, post-create hooks.
  - Orchestrate safe pruning: query PR statuses, identify merged worktrees, verify dirty state, remove worktrees, release ports, prune git metadata.

### Task 6: Rich CLI Suite (`worktreeforge.cli.main`)
- [x] Subtask 6.1: Implement `worktreeforge list`: Rich table with branch, path, lock status, allocated ports, and PR state.
- [x] Subtask 6.2: Implement `worktreeforge new <branch>`: Interactive creation with flags `--base`, `--path`, `--port-offset`, `--no-ports`, `--open`.
- [x] Subtask 6.3: Implement `worktreeforge remove <name_or_path>`: Safety verification and force option.
- [x] Subtask 6.4: Implement `worktreeforge lock` and `worktreeforge unlock`.
- [x] Subtask 6.5: Implement `worktreeforge ports`: Show active port mappings and live TCP socket checks.
- [x] Subtask 6.6: Implement `worktreeforge stash` subcommands: `list`, `show`, `search`, `apply`, `pop`, `drop`.
- [x] Subtask 6.7: Implement `worktreeforge prune`: Handle `--merged` and `--dry-run`.
- [x] Subtask 6.8: Implement `worktreeforge tui` launcher and `worktreeforge web` launcher.

### Task 7: Interactive Terminal Dashboard (TUI)
- [x] Subtask 7.1: Implement `src/worktreeforge/tui/app.py` using Textual:
  - Worktree data table with real-time status.
  - Action keys: `[n]` New worktree, `[d]` Delete worktree, `[l]` Lock/Unlock, `[s]` Stash viewer, `[p]` Prune merged, `[r]` Refresh, `[q]` Quit.
  - Interactive Stash modal with file selection and syntax-highlighted diff display.

### Task 8: Web Studio Dashboard (FastAPI + Modern Web UI)
- [x] Subtask 8.1: Implement `src/worktreeforge/web/server.py`:
  - REST endpoints for listing, creating, removing, locking, and pruning worktrees.
  - REST endpoints for listing, viewing diffs, searching, and applying stashes.
  - REST endpoints for port mapping and socket verification.
  - WebSocket endpoint `/ws` broadcasting filesystem changes and repo events in real time.
- [x] Subtask 8.2: Implement frontend (`index.html`, `style.css`, `app.js`):
  - Dark-mode developer interface.
  - Worktree cards with live port badges, PR status pills, lock toggles, and direct terminal/editor launcher buttons.
  - Embedded Stash Studio with file tree, diff viewer, and instant search.
  - Port multiplexer status panel with live listening indicators.

### Task 9: Comprehensive Automated Test Suite
- [x] Subtask 9.1: Git client tests with temporary git repositories (`test_git_client.py`).
- [x] Subtask 9.2: Port scanner and socket verifier tests (`test_port_scanner.py`, `test_port_allocator.py`).
- [x] Subtask 9.3: Environment patcher tests (`test_env_patcher.py`).
- [x] Subtask 9.4: Stash inspector and diff parser tests (`test_stash_inspector.py`).
- [x] Subtask 9.5: Supervisor and PR checker tests (`test_supervisor.py`, `test_github_pr_checker.py`).
- [x] Subtask 9.6: CLI commands test suite (`test_cli.py`).
- [x] Subtask 9.7: Web API test suite with FastAPI TestClient (`test_web_server.py`).

### Task 10: Visual Assets Generation & Portfolio Live Sync (Phase 2)
- [x] Subtask 10.1: Generate authentic high-resolution UI preview (`docs/images/worktreeforge_preview.png`).
- [x] Subtask 10.2: Generate animated demo GIF (`docs/images/worktreeforge_demo.gif`).
- [x] Subtask 10.3: Execute MTLG Portfolio Sync Phase 2: migrate assets to `mtlg-site` and `mtlglabs-space`, update `projects.json` to LIVE, run sync scripts, commit/push, and broadcast to X.
