# Git Worktree Workflows and Patterns

This guide outlines practical multi-worktree workflows for AI-assisted development, parallel bug fixes, and continuous review cycles.

## 1. Parallel AI Feature Development

When building features with AI coding assistants, agents often write code, run dev servers, and execute test suites simultaneously. Using multiple branches in a single directory forces constant checkouts and cache rebuilds.

```
                  +--------------------------------+
                  |  Main Repo (B:/workgit/webapp) |
                  |  Branch: main | Port: 3000     |
                  +---------------+----------------+
                                  |
         +------------------------+------------------------+
         |                                                 |
+--------v-----------------------+        +----------------v-----------------------+
| Worktree 1: ../webapp-refactor |        | Worktree 2: ../webapp-auth             |
| Branch: feat/refactor          |        | Branch: feat/oauth-providers           |
| Port: 3001 (.env.local)        |        | Port: 3002 (.env.local)                |
| AI Agent: Test coverage refactor|       | AI Agent: Auth flow implementation     |
+--------------------------------+        +----------------------------------------+
```

### Workflow steps

1. Create a worktree for the first task:
   ```bash
   worktreeforge new feat/refactor
   ```
   This generates `../webapp-refactor` and configures `PORT=3001` in its `.env.local`.

2. Create a worktree for the second task:
   ```bash
   worktreeforge new feat/oauth-providers
   ```
   This generates `../webapp-auth` and configures `PORT=3002` in its `.env.local`.

3. Launch dev servers in both directories without port collision:
   - In `../webapp-refactor`: runs on port 3001.
   - In `../webapp-auth`: runs on port 3002.

---

## 2. Fast Patch and Hotfix Interruption

When you are deep into an uncommitted feature on `feat/big-feature` and need to quickly verify and patch a production bug:

Instead of stashing uncommitted changes and switching branches:

1. Create a hotfix worktree:
   ```bash
   worktreeforge new hotfix/checkout-crash --base origin/main
   ```
2. Navigate to the new worktree, reproduce the bug, write tests, commit, and open a PR:
   ```bash
   cd ../webapp-hotfix-checkout-crash
   git commit -am "fix(checkout): validate null user session payload"
   gh pr create --fill
   ```
3. Return to your original worktree immediately. No files were touched in your main workspace.

---

## 3. Pull Request Review and Pruning

Once a pull request is merged on GitHub:

1. List worktrees to see their PR state:
   ```bash
   worktreeforge list
   ```
2. Any worktree with a merged PR is highlighted with `[MERGED]`.
3. Clean up all merged worktree directories safely:
   ```bash
   worktreeforge prune --merged
   ```
   WorktreeForge verifies that no uncommitted files exist before deleting the folder and executing `git worktree prune`.
