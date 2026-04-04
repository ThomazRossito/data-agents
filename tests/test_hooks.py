"""Testes dos hooks de segurança e auditoria."""

import pytest
import asyncio
from hooks.security_hook import block_destructive_commands


@pytest.mark.asyncio
async def test_blocks_rm_rf():
    result = await block_destructive_commands(
        {"tool_name": "Bash", "tool_input": {"command": "rm -rf /"}},
        tool_use_id="test-1",
        context=None,
    )
    assert "hookSpecificOutput" in result
    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.asyncio
async def test_blocks_drop_database():
    result = await block_destructive_commands(
        {"tool_name": "Bash", "tool_input": {"command": "DROP DATABASE prod"}},
        tool_use_id="test-2",
        context=None,
    )
    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.asyncio
async def test_allows_safe_command():
    result = await block_destructive_commands(
        {"tool_name": "Bash", "tool_input": {"command": "echo 'hello'"}},
        tool_use_id="test-3",
        context=None,
    )
    assert result == {}


@pytest.mark.asyncio
async def test_ignores_non_bash_tools():
    result = await block_destructive_commands(
        {"tool_name": "Read", "tool_input": {"file_path": "/tmp/test.py"}},
        tool_use_id="test-4",
        context=None,
    )
    assert result == {}
