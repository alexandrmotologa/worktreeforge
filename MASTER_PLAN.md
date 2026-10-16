# WorktreeForge: Master Implementation Plan

> **High-Speed Git Worktree Supervisor, Stash Studio & Local Port Multiplexer**
>
> *Supercharge parallel Git workflows without branch-switching friction. Instant worktree provisioning, automated local dev server port offset multiplexing (`PORT=3000`, `PORT=3001`), interactive stash visualizer, and automated merged-PR worktree cleanup.*

---

## 1. Project Overview & Architecture

Git Worktrees are one of Git's most potent features: they allow checking out multiple branches simultaneously into isolated directory trees. Developers can work on a new feature in one directory while fixing an urgent bug in another—without stashing, switching branches, or re-running slow `npm install` steps.

However, standard Git Worktrees suffer from major friction points:
1. **Port Collisions**: Running dev servers (e.g. Next.js, Vite, FastAPI) in two worktrees simultaneously fails with `Error: EADDRINUSE: address already in use :::3000`.
2. **Cumbersome CLI Syntax**: Creating, switching, and pruning worktrees requires verbose commands (`git worktree add -b feature-x ../repo-feature-x origin/main`).
3. **Orphaned Directories**: Merged branches leave abandoned directories that waste disk space and clutter `.git/worktrees/`.
4. **Stash Amnesia**: Git stashes are invisible stacks where uncommitted experiments get forgotten.

**WorktreeForge** transforms worktree operations into a seamless developer experience:
- **Instant Worktree Provisioning**: 1-command or 1-click worktree creation with automated branch checkout and symlink preservation.
- **Port Multiplexing Engine**: Automatically discovers port declarations in `.env`, `package.json`, or `docker-compose.yml` and assigns deterministic, collision-free port offsets (e.g. Base: 3000, Worktree 1: 3001, Worktree 2: 3002).
- **Interactive Stash Studio**: Searchable TUI & Web dashboard displaying diffs for all stashes with hunk-level cherry-picking.
- **GitHub PR Synchronization & Auto-Prune**: Connects with GitHub CLI (`gh`) to automatically detect when a PR is merged and safely cleans up the worktree.

```
+-----------------------------------------------------------------------------------+
|                                  WORKTREEFORGE                                    |
+-----------------------------------------+-----------------------------------------+
                                          |
        +---------------------------------+---------------------------------+
        |                                                                   |
+-------v-------------------------+                 +-----------------------v-------+
|    Worktree Lifecycle Manager   |                 |    Local Port Multiplexer     |
|  * Fast Multi-Branch Checkout   |                 |  * .env Auto-Configuration    |
|  * Directory Isolation          |                 |  * Dynamic Port Offsets       |
|  * Submodule & Dependency Link  |                 |  * Prevents EADDRINUSE Conflicts|
+-------+-------------------------+                 +-----------------------+-------+
        |                                                                   |
        +---------------------------------+---------------------------------+
                                          |
                        +-----------------v-----------------+
                        |       Visual Stash Studio         |
                        |  * Searchable Stash Hierarchy     |
                        |  * Hunk-Level Diff Viewer         |
                        |  * 1-Click Selective Pop / Apply  |
                        +-----------------+-----------------+
                                          |
                        +-----------------v-----------------+
                        |    GitHub PR Sync & Auto-Prune    |
                        |  * Merged PR Detection via `gh`   |
                        |  * Safe Unlink & Disk Reclamation |
                        |  * Interactive TUI & Web UI       |
                        +-----------------------------------+
```

---

## 2. Directory Structure

```
worktreeforge/
├── pyproject.toml
├── README.md
├── LICENSE
├── configs/
│   └── worktreeforge.default.yaml    # Port allocation ranges, base directories
├── docs/
│   ├── architecture.md
│   ├── cli-reference.md
│   └── worktree-workflows.md
├── src/
│   └── worktreeforge/
│       ├── __init__.py
│       ├── py.typed
│       ├── cli/
│       │   ├── __init__.py
│       │   └── main.py
│       ├── core/
│       │   ├── __init__.py
│       │   ├── config.py             # User preferences & workspace settings
│       │   ├── git_client.py         # Subprocess Git CLI wrapper (worktree, stash, branch)
│       │   ├── models.py             # WorktreeInfo, StashInfo, PortMapping
│       │   └── pruner.py             # Safe directory cleanup and git worktree prune
│       ├── multiplexer/
│       │   ├── __init__.py
│       │   ├── port_allocator.py     # Port reservation table & socket availability check
│       │   └── env_patcher.py        # Updates .env, .env.local with allocated ports
│       ├── stash/
│       │   ├── __init__.py
│       │   └── inspector.py          # Parses git stash list and unified diffs
│       ├── github/
│       │   ├── __init__.py
│       │   └── pr_checker.py         # Interrogates `gh pr status` for merged branches
│       ├── tui/
│       │   ├── __init__.py
│       │   └── app.py                # Textual interactive terminal dashboard
│       └── web/
│           ├── __init__.py
│           ├── server.py             # FastAPI backend with WebSocket file watchers
│           └── static/               # Worktree switcher canvas with live port badges
└── tests/
    ├── test_git_client.py
    ├── test_port_allocator.py
    ├── test_env_patcher.py
    ├── test_stash_inspector.py
    └── test_cli.py
```

---

## 3. Step-by-Step Implementation Roadmap

### Phase 1: Git Worktree Engine & Domain Models (`src/worktreeforge/core/`)
- Wrap Git native CLI commands:
  - `git worktree list --porcelain`: Parses path, HEAD commit, branch reference, locked state.
  - `git worktree add <path> <branch>`: Provisions new working tree with branch checkout.
  - `git worktree remove <path>` and `git worktree prune`.
- Handle dirty state validation: Prevents accidental deletion of uncommitted changes.

### Phase 2: Dynamic Port Multiplexer (`src/worktreeforge/multiplexer/`)
- Scan target repository for declared ports:
  - RegEx inspection of `.env`, `.env.example`, `.env.local`: `PORT=3000`, `SERVER_PORT=8000`.
  - JSON inspection of `package.json` scripts: `"dev": "next dev -p 3000"`.
- Assign sequential port slots:
  - Base Worktree: Port `3000`
  - Worktree 1 (`feature-auth`): Port `3001`
  - Worktree 2 (`bugfix-payments`): Port `3002`
- Verify socket availability before assignment (`socket.create_server()`).
- Auto-generate `.env.local` inside the newly created worktree directory with overridden ports.

### Phase 3: Interactive Stash Studio (`src/worktreeforge/stash/`)
- Parse `git stash list` with commit hashes, relative creation timestamps, and branch origin.
- Parse `git stash show -p stash@{n}` to generate syntax-highlighted diffs per file.
- Support operations:
  - `worktreeforge stash search <keyword>`
  - `worktreeforge stash apply <index> [--drop]`

### Phase 4: GitHub PR Auto-Pruner (`src/worktreeforge/github/`)
- Query GitHub CLI: `gh pr view <branch> --json state,mergedAt`.
- If the PR is merged:
  - Mark worktree with `[MERGED]` badge in CLI/TUI.
  - Provide 1-command cleanup: `worktreeforge prune --merged` which safely deletes the folder and runs `git worktree prune`.

### Phase 5: CLI Suite & Dual Dashboards
- CLI commands:
  - `worktreeforge new <branch-name>`: Interactively creates worktree, sets ports, and opens in editor.
  - `worktreeforge list`: Formatted table showing path, branch, active ports, and git status.
  - `worktreeforge tui`: Interactive Textual console for switching worktrees with arrow keys.
  - `worktreeforge web --port 8990`: Visual dashboard with 1-click terminal and editor launchers.

---

## 4. Agent Kickoff Prompt (Copy-Paste Ready)

```markdown
You are building WorktreeForge from scratch.

WorktreeForge is a high-speed Git worktree supervisor, stash studio, and local port multiplexer.
It automates parallel Git branch checkouts, prevents EADDRINUSE port conflicts by injecting sequential port offsets into .env files, and provides an interactive TUI for switching worktrees.

Follow these rules:
1. All code, comments, commit messages, and docs must be in English.
2. Zero mocks or placeholder implementations. Write authentic Git CLI subprocess interactions, socket port checks, and .env parser/patcher.
3. Keep test coverage high with pytest.
4. Provide a rich CLI with Typer and an interactive Web Studio with FastAPI.

Begin by setting up the repository in `B:\workgit\worktreeforge`, initialize git, write the core schemas in `src/worktreeforge/core/models.py`, and implement the Git worktree wrapper and port allocator.
```
