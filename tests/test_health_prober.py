"""Tests for health prober and shell integration."""

from worktreeforge.cli.shell_init import generate_shell_script
from worktreeforge.multiplexer.health_prober import probe_http_health


def test_probe_http_health_inactive():
    res = probe_http_health(port=61234, timeout=0.2)
    assert res["is_http_ok"] is False
    assert res["status_code"] is None


def test_generate_shell_script_pwsh():
    pwsh_script = generate_shell_script("pwsh")
    assert "function wtf" in pwsh_script
    assert "Set-Location" in pwsh_script


def test_generate_shell_script_bash():
    bash_script = generate_shell_script("bash")
    assert "wtf()" in bash_script
    assert "command worktreeforge" in bash_script
