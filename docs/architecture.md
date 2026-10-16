# Architecture Overview

WorktreeForge is structured into modular layers that separate Git process execution, local networking allocation, stash management, GitHub synchronization, and user interfaces (CLI, TUI, Web).

```
+----------------------------------------------------------------------------------+
|                            User Interfaces & Presentation                         |
|   CLI (Typer + Rich)   |   TUI Dashboard (Textual)   |   Web Studio (FastAPI)     |
+----------------------------------------------------------------------------------+
                                        |
+----------------------------------------------------------------------------------+
|                              Application Core Layer                              |
|   WorktreeSupervisor   |   ConfigManager   |   PRChecker (gh)  |  StashInspector  |
+----------------------------------------------------------------------------------+
                                        |
+----------------------------------------------------------------------------------+
|                        Multiplexer & Environment Layer                           |
|   PortScanner          |   SocketVerifier  |   PortRegistry    |  EnvPatcher     |
+----------------------------------------------------------------------------------+
                                        |
+----------------------------------------------------------------------------------+
|                          System & Process Adapters                               |
|   GitCLI Subprocess    |   File Watchers   |   TCP Socket APIs |  OS Filesystem  |
+----------------------------------------------------------------------------------+
```

## Subsystems

### 1. Core Git Adapter (`worktreeforge.core.git_client`)
- Interacts with Git through standard subprocess execution.
- Parses `git worktree list --porcelain` to capture path, commit HEAD, branch reference, bare status, and locked state.
- Executes `git worktree add`, `git worktree remove`, `git worktree lock`, and `git worktree prune`.
- Evaluates repository dirty state via `git status --porcelain` before executing destructive actions.

### 2. Port Multiplexer (`worktreeforge.multiplexer`)
- **Port Scanner (`port_allocator.py`)**: Reads `.env`, `.env.example`, `.env.local`, and `package.json` to extract declared port numbers and environment variable names (`PORT`, `VITE_PORT`, `SERVER_PORT`).
- **Socket Verifier**: Attempts temporary non-blocking TCP socket creation (`socket.socket(socket.AF_INET, socket.SOCK_STREAM)`) with `SO_REUSEADDR` disabled to ensure the candidate port is free.
- **Port Registry (`models.py`)**: Stores active worktree-to-port mappings in `.worktreeforge.ports.json` at the repository root.
- **Environment Patcher (`env_patcher.py`)**: Generates or updates `.env.local` inside the worktree directory, preserving existing variables while overriding allocated ports.

### 3. Stash Studio (`worktreeforge.stash.inspector`)
- Extracts stashes using `git stash list --pretty=format:...` with stash index, author, timestamp, branch, and subject.
- Generates file-level breakdowns and unified diffs per stash entry using `git stash show -p`.
- Supports full-text search across diff content and stash summaries.

### 4. GitHub PR Auto-Pruner (`worktreeforge.github.pr_checker`)
- Checks pull request state using GitHub CLI (`gh pr view <branch> --json state,mergedAt,url`).
- Distinguishes between `OPEN`, `MERGED`, `CLOSED`, and `NO_PR`.
- Flags merged worktrees for safe pruning and disk space reclamation.

### 5. Interfaces
- **CLI (`worktreeforge.cli`)**: Terminal commands with Rich formatting, color status badges, and tables.
- **TUI (`worktreeforge.tui`)**: Interactive Textual application allowing keyboard navigation, live diff inspection, and one-key branch switching.
- **Web Studio (`worktreeforge.web`)**: FastAPI server providing REST endpoints, WebSocket event streams, and a browser dashboard.
