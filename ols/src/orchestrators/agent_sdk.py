"""Agent SDK orchestrator for native SDK-based agent execution."""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, AsyncGenerator, Optional

from ols import config, constants
from ols.app.models.models import ChunkType, StreamedChunk, SummarizerResponse
from ols.src.orchestrators.prompts import (
    ANALYSIS_SYSTEM_PROMPT,
    EXECUTION_SYSTEM_PROMPT,
    RBAC_EVALUATION_SYSTEM_PROMPT,
    VERIFICATION_SYSTEM_PROMPT,
    build_escalation_prompt,
)
from ols.src.orchestrators.schemas import MODE_OUTPUT_SCHEMAS
from ols.utils.async_utils import (
    drain_generate_response,
    resolve_system_prompt,
    run_async_safely,
)
from ols.utils.checks import InvalidConfigurationError

if TYPE_CHECKING:
    from langchain_core.messages import BaseMessage
    from llama_index.core.retrievers import BaseRetriever

logger = logging.getLogger(__name__)

# Module-level mode→config mappings (avoid per-request dict creation)
_MODE_PROMPTS: dict[str, str] = {
    constants.MODE_DESIGN: ANALYSIS_SYSTEM_PROMPT,
    constants.MODE_MONITOR: ANALYSIS_SYSTEM_PROMPT,
    constants.MODE_REMEDIATE: ANALYSIS_SYSTEM_PROMPT,
    constants.MODE_DEPLOY: EXECUTION_SYSTEM_PROMPT,
    constants.MODE_VERIFY: VERIFICATION_SYSTEM_PROMPT,
    constants.MODE_RBAC_EVALUATION: RBAC_EVALUATION_SYSTEM_PROMPT,
}

_MODE_TOOLS: dict[str, list[str]] = {
    constants.MODE_DESIGN: constants.AGENT_SDK_DESIGN_TOOLS,
    constants.MODE_DEPLOY: constants.AGENT_SDK_WRITE_TOOLS,
    constants.MODE_MONITOR: constants.AGENT_SDK_MONITOR_TOOLS,
    constants.MODE_REMEDIATE: constants.AGENT_SDK_READONLY_TOOLS,
    constants.MODE_ESCALATE: constants.AGENT_SDK_ESCALATION_TOOLS,
    constants.MODE_VERIFY: constants.AGENT_SDK_VERIFY_TOOLS,
    constants.MODE_RBAC_EVALUATION: constants.AGENT_SDK_RBAC_EVALUATION_TOOLS,
}

_MODE_OUTPUT_FORMATS: dict[str, dict[str, Any]] = {
    mode: {"type": "json_schema", "schema": schema}
    for mode, schema in MODE_OUTPUT_SCHEMAS.items()
}


@dataclass(frozen=True, slots=True)
class BackendRunConfig:
    """Configuration passed to agent SDK backends for a single run.

    Groups the parameters needed by backends so the ``run()`` signature
    stays stable as new fields are added.
    """

    query: str
    system_prompt: str
    history: list[BaseMessage]
    model: str
    credentials: Optional[str]
    provider_url: Optional[str]
    max_tokens: int
    max_iterations: int
    mode: str = constants.MODE_QA
    tools: list[str] = field(default_factory=lambda: list(constants.AGENT_SDK_DEFAULT_TOOLS))
    output_format: Optional[dict[str, Any]] = None


class AgentSDKBackend(ABC):
    """Base class for agent SDK backends.

    Each backend wraps a specific agent SDK (Anthropic, OpenAI, Google ADK)
    and translates its events into the OLS StreamedChunk protocol.

    Subclasses must implement ``run`` which drives the SDK's agent loop
    and yields StreamedChunk objects that the orchestrator forwards to
    the endpoint layer unchanged.
    """

    @abstractmethod
    async def run(
        self,
        run_config: BackendRunConfig,
    ) -> AsyncGenerator[StreamedChunk, None]:
        """Run the agent loop and yield streamed chunks.

        Args:
            run_config: All parameters needed for the agent run.

        Yields:
            StreamedChunk objects (TEXT, TOOL_CALL, TOOL_RESULT).
        """
        ...  # pragma: no cover
        yield  # pragma: no cover  # make this a generator


class AnthropicAgentBackend(AgentSDKBackend):
    """Backend using the Claude Agent SDK (claude-agent-sdk).

    Uses the Claude Agent SDK ``query()`` function which provides the same
    autonomous agent loop as Claude Code: built-in tools for file I/O,
    shell commands, web search, and MCP server integration.

    The SDK handles tool execution autonomously — no external RAG pipeline
    or MCP tool injection is needed. The agent can read files, search
    codebases, and run commands on its own.

    Authentication is handled via environment variables:
      - Direct API: ``ANTHROPIC_API_KEY``
      - Google Vertex AI: ``CLAUDE_CODE_USE_VERTEX=1`` + ADC
      - Amazon Bedrock: ``CLAUDE_CODE_USE_BEDROCK=1`` + AWS creds

    Requires: pip install claude-agent-sdk
    """

    @staticmethod
    def _langchain_history_to_prompt(
        query_text: str,
        history: list[BaseMessage],
    ) -> str:
        """Convert LangChain history + query into a single prompt string."""
        if not history:
            return query_text
        parts: list[str] = []
        for msg in history:
            role = "User" if msg.type == "human" else "Assistant"
            parts.append(f"{role}: {msg.content}")
        parts.append(f"User: {query_text}")
        return "\n\n".join(parts)

    @staticmethod
    def _chunks_from_assistant(
        msg: Any,
        round_index: int,
    ) -> tuple[list[StreamedChunk], int]:
        """Extract StreamedChunks from an AssistantMessage."""
        chunks: list[StreamedChunk] = []
        for block in msg.content:
            if hasattr(block, "text") and block.text:
                chunks.append(StreamedChunk(type=ChunkType.TEXT, text=block.text))
            elif hasattr(block, "name"):
                round_index += 1
                chunks.append(
                    StreamedChunk(
                        type=ChunkType.TOOL_CALL,
                        data={
                            "name": block.name,
                            "args": getattr(block, "input", {}),
                            "id": getattr(block, "id", "unknown"),
                            "type": ChunkType.TOOL_CALL.value,
                        },
                    )
                )
        return chunks, round_index

    @staticmethod
    def _chunks_from_tool_result(msg: Any, round_index: int) -> list[StreamedChunk]:
        """Extract StreamedChunks from a tool result message."""
        chunks: list[StreamedChunk] = []
        if not hasattr(msg, "content"):
            return chunks
        for block in msg.content:
            raw_content = getattr(block, "content", "")
            content = raw_content if isinstance(raw_content, str) else str(raw_content)
            chunks.append(
                StreamedChunk(
                    type=ChunkType.TOOL_RESULT,
                    data={
                        "id": getattr(block, "tool_use_id", "unknown"),
                        "name": getattr(block, "name", "tool"),
                        "status": "success",
                        "content": content,
                        "type": ChunkType.TOOL_RESULT.value,
                        "round": round_index,
                    },
                )
            )
        return chunks

    async def run(
        self,
        run_config: BackendRunConfig,
    ) -> AsyncGenerator[StreamedChunk, None]:
        """Run Claude Agent SDK loop.

        Delegates to ``claude_agent_sdk.query()`` which handles the full
        agent loop autonomously — tool calls, multi-turn reasoning, etc.
        Streams events back as OLS StreamedChunk objects.
        """
        from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage
        from claude_agent_sdk import query as sdk_query

        user_prompt = self._langchain_history_to_prompt(
            run_config.query, run_config.history
        )

        options = ClaudeAgentOptions(
            model=run_config.model,
            system_prompt=run_config.system_prompt,
            max_turns=run_config.max_iterations,
            permission_mode=constants.AGENT_SDK_PERMISSION_MODE,
            allowed_tools=run_config.tools,
            output_format=run_config.output_format,
        )

        round_index = 0
        async for msg in sdk_query(prompt=user_prompt, options=options):
            if isinstance(msg, ResultMessage):
                if msg.structured_output is not None:
                    yield StreamedChunk(
                        type=ChunkType.TEXT,
                        data={"structured_output": msg.structured_output},
                    )
            elif isinstance(msg, AssistantMessage):
                chunks, round_index = self._chunks_from_assistant(msg, round_index)
                for chunk in chunks:
                    yield chunk
            elif hasattr(msg, "content"):
                for chunk in self._chunks_from_tool_result(msg, round_index):
                    yield chunk


class OpenAIAgentBackend(AgentSDKBackend):
    """Backend using the OpenAI Agents SDK (openai-agents).

    Requires: pip install openai-agents
    """

    async def run(
        self,
        run_config: BackendRunConfig,
    ) -> AsyncGenerator[StreamedChunk, None]:
        """Run OpenAI Agents SDK loop."""
        raise NotImplementedError(
            "OpenAI Agents SDK backend is not yet implemented. "
            "Install openai-agents and implement this backend."
        )
        yield  # pragma: no cover  # make this a generator


class GoogleADKBackend(AgentSDKBackend):
    """Backend using the Google Agent Development Kit (google-adk).

    Requires: pip install google-adk
    """

    async def run(
        self,
        run_config: BackendRunConfig,
    ) -> AsyncGenerator[StreamedChunk, None]:
        """Run Google ADK agent loop."""
        raise NotImplementedError(
            "Google ADK backend is not yet implemented. "
            "Install google-adk and implement this backend."
        )
        yield  # pragma: no cover  # make this a generator


_BACKENDS: dict[str, type[AgentSDKBackend]] = {
    constants.AGENT_SDK_BACKEND_ANTHROPIC: AnthropicAgentBackend,
    constants.AGENT_SDK_BACKEND_OPENAI: OpenAIAgentBackend,
    constants.AGENT_SDK_BACKEND_GOOGLE_ADK: GoogleADKBackend,
}


class AgentSDKOrchestrator:
    """Orchestrator that delegates to native agent SDK backends.

    Unlike the LangChain-based DocsSummarizer, this orchestrator does NOT
    use the OLS RAG pipeline or MCP tool system. The agent SDKs have their
    own built-in tools (file I/O, shell, web search) and handle tool
    execution autonomously.

    It conforms to the same interface as DocsSummarizer (generate_response /
    create_response) so it can be used as a drop-in replacement via the factory.
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        user_token: Optional[str] = None,
        client_headers: Any = None,
        streaming: bool = False,
        backend_type: str = constants.AGENT_SDK_BACKEND_ANTHROPIC,
        mode: str = constants.MODE_QA,
    ) -> None:
        """Initialize the AgentSDKOrchestrator.

        Args:
            provider: LLM provider name.
            model: Model name.
            system_prompt: Optional system prompt override.
            user_token: Accepted for interface compatibility (unused).
            client_headers: Accepted for interface compatibility (unused).
            streaming: Whether this orchestrator is used for streaming.
            backend_type: Which agent SDK backend to use.
            mode: Capability mode (qa, design, remediate, etc.).
        """
        self.provider = provider or config.ols_config.default_provider
        self.model = model or config.ols_config.default_model
        self.streaming = streaming
        self.mode = mode

        self._system_prompt = self._resolve_mode_prompt(system_prompt)
        self._tools = self._resolve_mode_tools()
        self._output_format = self._resolve_mode_schema()

        self.provider_config = config.llm_config.providers.get(self.provider)
        if self.provider_config is None:
            raise InvalidConfigurationError(f"unknown provider: {self.provider!r}")
        self.model_config = self.provider_config.models.get(self.model)
        if self.model_config is None:
            raise InvalidConfigurationError(
                f"unknown model: {self.model!r} for provider {self.provider!r}"
            )

        self._provider_url = (
            str(self.provider_config.url) if self.provider_config.url else None
        )

        backend_cls = _BACKENDS.get(backend_type)
        if backend_cls is None:
            raise InvalidConfigurationError(
                f"unknown agent SDK backend: {backend_type!r}, "
                f"supported backends are {set(_BACKENDS.keys())}"
            )
        self._backend = backend_cls()

        logger.info(
            "AgentSDKOrchestrator initialized: provider=%s, model=%s, backend=%s, mode=%s",
            self.provider,
            self.model,
            backend_type,
            self.mode,
        )

    def _resolve_mode_prompt(self, system_prompt_override: Optional[str]) -> str:
        """Resolve system prompt based on mode."""
        if config.dev_config.enable_system_prompt_override and system_prompt_override:
            return system_prompt_override

        if self.mode == constants.MODE_ESCALATE:
            target_repo = os.environ.get(
                constants.ESCALATION_TARGET_REPO_ENV_VAR,
                constants.DEFAULT_ESCALATION_TARGET_REPO,
            )
            return build_escalation_prompt(target_repo)

        if self.mode in _MODE_PROMPTS:
            return _MODE_PROMPTS[self.mode]
        return resolve_system_prompt(system_prompt_override)

    def _resolve_mode_tools(self) -> list[str]:
        """Resolve tool set based on mode."""
        return list(_MODE_TOOLS.get(self.mode, constants.AGENT_SDK_DEFAULT_TOOLS))

    def _resolve_mode_schema(self) -> Optional[dict[str, Any]]:
        """Resolve structured output schema based on mode."""
        return _MODE_OUTPUT_FORMATS.get(self.mode)

    async def generate_response(
        self,
        query: str,
        rag_retriever: Optional[BaseRetriever] = None,
        history: Optional[list[BaseMessage]] = None,
    ) -> AsyncGenerator[StreamedChunk, None]:
        """Generate a streaming response using the agent SDK backend.

        The rag_retriever parameter is accepted for interface compatibility
        but is not used — agent SDK backends find context autonomously.

        Args:
            query: The query to be answered.
            rag_retriever: Accepted for interface compatibility (unused).
            history: Optional conversation history.

        Yields:
            StreamedChunk objects representing parts of the response.
        """
        run_config = BackendRunConfig(
            query=query,
            system_prompt=self._system_prompt,
            history=history if history is not None else [],
            model=self.model,
            credentials=self.provider_config.credentials,
            provider_url=self._provider_url,
            max_tokens=self.model_config.parameters.max_tokens_for_response,
            max_iterations=config.ols_config.max_iterations,
            mode=self.mode,
            tools=self._tools,
            output_format=self._output_format,
        )

        async for chunk in self._backend.run(run_config):
            yield chunk

        yield StreamedChunk(
            type=ChunkType.END,
            data={
                "rag_chunks": [],
                "truncated": False,
                "token_counter": None,
            },
        )

    def create_response(
        self,
        query: str,
        rag_retriever: Optional[BaseRetriever] = None,
        history: Optional[list[BaseMessage]] = None,
    ) -> SummarizerResponse:
        """Generate a synchronous response using the agent SDK backend.

        Drains the async streaming generator into a SummarizerResponse.
        """
        return run_async_safely(
            drain_generate_response(
                self.generate_response(query, rag_retriever, history)
            )
        )
