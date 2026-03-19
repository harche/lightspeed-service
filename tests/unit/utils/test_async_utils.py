"""Unit tests for async utilities."""

import pytest

from ols import config
from ols.app.models.models import ChunkType, StreamedChunk, SummarizerResponse
from ols.utils.async_utils import (
    drain_generate_response,
    resolve_system_prompt,
    run_async_safely,
)


@pytest.fixture(scope="function", autouse=True)
def _setup():
    """Load a valid config for tests."""
    config.reload_from_yaml_file("tests/config/valid_config_without_mcp.yaml")


@pytest.mark.asyncio
async def test_drain_generate_response_text_only():
    """Test draining a generator with only text chunks."""

    async def gen():
        yield StreamedChunk(type=ChunkType.TEXT, text="hello ")
        yield StreamedChunk(type=ChunkType.TEXT, text="world")
        yield StreamedChunk(
            type=ChunkType.END,
            data={"rag_chunks": [], "truncated": False, "token_counter": None},
        )

    result = await drain_generate_response(gen())
    assert isinstance(result, SummarizerResponse)
    assert result.response == "hello world"
    assert result.rag_chunks == []
    assert result.history_truncated is False
    assert result.tool_calls == []
    assert result.tool_results == []


@pytest.mark.asyncio
async def test_drain_generate_response_with_tools():
    """Test draining a generator with tool call and result chunks."""

    async def gen():
        yield StreamedChunk(type=ChunkType.TOOL_CALL, data={"name": "t1", "id": "1"})
        yield StreamedChunk(
            type=ChunkType.TOOL_RESULT,
            data={"id": "1", "status": "success", "content": "ok"},
        )
        yield StreamedChunk(type=ChunkType.TEXT, text="done")
        yield StreamedChunk(
            type=ChunkType.END,
            data={"rag_chunks": [], "truncated": False, "token_counter": None},
        )

    result = await drain_generate_response(gen())
    assert result.response == "done"
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0]["name"] == "t1"
    assert len(result.tool_results) == 1
    assert result.tool_results[0]["status"] == "success"


@pytest.mark.asyncio
async def test_drain_generate_response_empty():
    """Test draining a generator that yields only END."""

    async def gen():
        yield StreamedChunk(
            type=ChunkType.END,
            data={"rag_chunks": [], "truncated": True, "token_counter": None},
        )

    result = await drain_generate_response(gen())
    assert result.response == ""
    assert result.history_truncated is True


def test_run_async_safely_runs_coroutine():
    """Test that run_async_safely executes a coroutine and returns its result."""

    async def coro():
        return 42

    assert run_async_safely(coro()) == 42


def test_resolve_system_prompt_returns_config_value():
    """Test that resolve_system_prompt returns the config system prompt."""
    result = resolve_system_prompt()
    assert result == config.ols_config.system_prompt


def test_resolve_system_prompt_uses_default_when_no_config():
    """Test fallback to QUERY_SYSTEM_INSTRUCTION when config is None."""
    from ols.src.prompts.prompts import QUERY_SYSTEM_INSTRUCTION

    original = config.ols_config.system_prompt
    config.ols_config.system_prompt = None
    try:
        result = resolve_system_prompt()
        assert result == QUERY_SYSTEM_INSTRUCTION
    finally:
        config.ols_config.system_prompt = original


def test_resolve_system_prompt_override_disabled():
    """Test that override is ignored when dev config disables it."""
    config.dev_config.enable_system_prompt_override = False
    result = resolve_system_prompt("custom prompt")
    assert result == config.ols_config.system_prompt
    assert result != "custom prompt"
