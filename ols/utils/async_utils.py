"""Shared utilities for orchestrators."""

import asyncio
import logging
from typing import Any, AsyncGenerator, Coroutine, Optional

from ols import config
from ols.app.models.models import ChunkType, StreamedChunk, SummarizerResponse
from ols.src.prompts.prompts import QUERY_SYSTEM_INSTRUCTION

logger = logging.getLogger(__name__)


def resolve_system_prompt(system_prompt: Optional[str] = None) -> str:
    """Resolve the system prompt from override, config, or default.

    Shared by both DocsSummarizer (via QueryHelper) and AgentSDKOrchestrator.

    Args:
        system_prompt: Optional override provided by the caller.

    Returns:
        The resolved system prompt string.
    """
    return (
        (config.dev_config.enable_system_prompt_override and system_prompt)
        or config.ols_config.system_prompt
        or QUERY_SYSTEM_INSTRUCTION
    )


def run_async_safely(coro: Coroutine[Any, Any, Any]) -> Any:
    """Run an async coroutine, handling the case where a loop is already running."""
    try:
        return asyncio.run(coro)
    except RuntimeError as e:
        if "already running" in str(e).lower():
            logger.warning("Using existing event loop as one is already running")
            return asyncio.get_event_loop().run_until_complete(coro)
        raise


async def drain_generate_response(
    generator: AsyncGenerator[StreamedChunk, None],
) -> SummarizerResponse:
    """Collect all streamed chunks into a single SummarizerResponse.

    Shared utility used by both DocsSummarizer and AgentSDKOrchestrator
    to drain a streaming generator into a SummarizerResponse.

    Args:
        generator: Async generator yielding StreamedChunk objects.

    Returns:
        Aggregated SummarizerResponse.
    """
    chunks: list[str] = []
    response_end: dict[str, object] = {}
    tool_calls: list[dict[str, object]] = []
    tool_results: list[dict[str, object]] = []
    async for chunk in generator:
        match chunk.type:
            case ChunkType.END:
                response_end = chunk.data
                break
            case ChunkType.TOOL_CALL:
                tool_calls.append(chunk.data)
            case ChunkType.TOOL_RESULT:
                tool_results.append(chunk.data)
            case ChunkType.TEXT:
                chunks.append(chunk.text)
            case _:
                msg = f"Unknown chunk type: {chunk.type}"
                logger.warning(msg)
                raise ValueError(msg)

    return SummarizerResponse(
        response="".join(chunks),
        rag_chunks=response_end.get("rag_chunks", []),
        history_truncated=response_end.get("truncated", False),
        token_counter=response_end.get("token_counter", None),
        tool_calls=tool_calls,
        tool_results=tool_results,
    )
