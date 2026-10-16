"""Shell integration generators for instant worktree navigation."""

import sys


PWSH_SCRIPT = """# WorktreeForge PowerShell Integration
function wtf {
    param([Parameter(ValueFromRemainingArguments=$true)]$ArgsList)
    if ($ArgsList.Count -ge 2 -and $ArgsList[0] -eq "cd") {
        $target = $ArgsList[1]
        $targetPath = & worktreeforge path $target 2>$null
        if ($LASTEXITCODE -eq 0 -and $targetPath -and (Test-Path $targetPath.Trim())) {
            Set-Location $targetPath.Trim()
        } else {
            Write-Host "WorktreeForge: Worktree '$target' not found." -ForegroundColor Red
        }
    } else {
        & worktreeforge @ArgsList
    }
}
Set-Alias -Name worktree -Value wtf -Scope Global -ErrorAction SilentlyContinue
"""

BASH_ZSH_SCRIPT = """# WorktreeForge Bash/Zsh Integration
wtf() {
    if [ "$1" = "cd" ]; then
        if [ -z "$2" ]; then
            echo "WorktreeForge: Usage: wtf cd <branch>" >&2
            return 1
        fi
        local target_path
        target_path="$(worktreeforge path "$2" 2>/dev/null)"
        if [ $? -eq 0 ] && [ -n "$target_path" ] && [ -d "$target_path" ]; then
            cd "$target_path" || return 1
        else
            echo "WorktreeForge: Worktree '$2' not found." >&2
            return 1
        fi
    else
        command worktreeforge "$@"
    fi
}
alias worktree=wtf
"""


def generate_shell_script(shell: str) -> str:
    """Return hook script for target shell."""
    s = shell.strip().lower()
    if s in ("pwsh", "powershell", "ps"):
        return PWSH_SCRIPT.strip()
    return BASH_ZSH_SCRIPT.strip()
