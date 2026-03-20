"""Factory for creating orchestrators."""

import logging
from collections.abc import Callable
from typing import Any, Optional

from langchain_core.language_models.llms import LLM

from ols import config, constants
from ols.utils.mcp_utils import ClientHeaders

logger = logging.getLogger(__name__)


def create_orchestrator(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    system_prompt: Optional[str] = None,
    user_token: Optional[str] = None,
    client_headers: Optional[ClientHeaders] = None,
    streaming: bool = False,
    llm_loader: Optional[Callable[[str, str, dict], LLM]] = None,
    mode: Optional[str] = None,
) -> Any:
    """Create the appropriate orchestrator based on configuration.

    When orchestrator_type is "langchain" (the default), returns a
    DocsSummarizer which uses LangChain for LLM invocation and tool calling.

    When orchestrator_type is "agent_sdk", returns an AgentSDKOrchestrator
    which delegates to a native agent SDK backend (Anthropic, OpenAI, or
    Google ADK).

    Args:
        provider: LLM provider name.
        model: Model name.
        system_prompt: Optional system prompt override.
        user_token: User authentication token for MCP tool access.
        client_headers: Client-provided MCP headers for authentication.
        streaming: Whether this orchestrator is used for the streaming endpoint.
        llm_loader: Optional LLM loader callable (used by LangChain path).

    Returns:
        An orchestrator with generate_response and create_response methods.
    """
    orchestrator_type = getattr(
        config.ols_config, "orchestrator_type", constants.ORCHESTRATOR_LANGCHAIN
    )

    if orchestrator_type == constants.ORCHESTRATOR_AGENT_SDK:
        # Lazy import: claude-agent-sdk is an optional dependency
        from ols.src.orchestrators.agent_sdk import AgentSDKOrchestrator

        backend_type = getattr(
            config.ols_config,
            "agent_sdk_backend",
            constants.AGENT_SDK_BACKEND_ANTHROPIC,
        )
        resolved_mode = mode or constants.MODE_QA
        logger.info(
            "Creating AgentSDKOrchestrator with backend=%s, mode=%s",
            backend_type,
            resolved_mode,
        )
        return AgentSDKOrchestrator(
            provider=provider,
            model=model,
            system_prompt=system_prompt,
            user_token=user_token,
            client_headers=client_headers,
            streaming=streaming,
            backend_type=backend_type,
            mode=resolved_mode,
        )

    # Lazy import: DocsSummarizer triggers the auth dependency chain at import time
    from ols.src.query_helpers.docs_summarizer import DocsSummarizer

    logger.debug("Creating LangChain orchestrator (DocsSummarizer)")
    kwargs: dict[str, Any] = {
        "provider": provider,
        "model": model,
        "system_prompt": system_prompt,
        "user_token": user_token,
        "client_headers": client_headers,
        "streaming": streaming,
    }
    if llm_loader is not None:
        kwargs["llm_loader"] = llm_loader
    return DocsSummarizer(**kwargs)
