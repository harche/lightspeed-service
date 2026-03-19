"""Unit tests for the AgentSDKOrchestrator."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from ols import config, constants
from ols.src.orchestrators.agent_sdk import (
    AgentSDKBackend,
    AgentSDKOrchestrator,
    AnthropicAgentBackend,
    BackendRunConfig,
    GoogleADKBackend,
    OpenAIAgentBackend,
)
from ols.utils.checks import InvalidConfigurationError


@pytest.fixture(scope="function", autouse=True)
def _setup():
    """Load a valid config for tests."""
    config.reload_from_yaml_file("tests/config/valid_config_without_mcp.yaml")


@pytest.fixture()
def _sample_run_config():
    """Create a minimal BackendRunConfig for testing."""
    return BackendRunConfig(
        query="test",
        system_prompt="test",
        history=[],
        model="test",
        credentials=None,
        provider_url=None,
        max_tokens=100,
        max_iterations=3,
    )


def test_unknown_backend_raises_configuration_error():
    """Test that an unknown backend type raises InvalidConfigurationError."""
    with pytest.raises(InvalidConfigurationError, match="unknown agent SDK backend"):
        AgentSDKOrchestrator(backend_type="nonexistent")


def test_unknown_provider_raises_configuration_error():
    """Test that an unknown provider raises InvalidConfigurationError."""
    with pytest.raises(InvalidConfigurationError, match="unknown provider"):
        AgentSDKOrchestrator(provider="nonexistent")


def test_unknown_model_raises_configuration_error():
    """Test that an unknown model raises InvalidConfigurationError."""
    with pytest.raises(InvalidConfigurationError, match="unknown model"):
        AgentSDKOrchestrator(provider="p1", model="nonexistent")


def test_anthropic_backend_instantiation():
    """Test that the Anthropic backend is selected correctly."""
    orchestrator = AgentSDKOrchestrator(
        backend_type=constants.AGENT_SDK_BACKEND_ANTHROPIC
    )
    assert isinstance(orchestrator._backend, AnthropicAgentBackend)


def test_openai_backend_instantiation():
    """Test that the OpenAI backend is selected correctly."""
    orchestrator = AgentSDKOrchestrator(backend_type=constants.AGENT_SDK_BACKEND_OPENAI)
    assert isinstance(orchestrator._backend, OpenAIAgentBackend)


def test_google_adk_backend_instantiation():
    """Test that the Google ADK backend is selected correctly."""
    orchestrator = AgentSDKOrchestrator(
        backend_type=constants.AGENT_SDK_BACKEND_GOOGLE_ADK
    )
    assert isinstance(orchestrator._backend, GoogleADKBackend)


def test_history_to_prompt_no_history():
    """Test prompt building returns query unchanged when no history."""
    result = AnthropicAgentBackend._langchain_history_to_prompt("hello", [])
    assert result == "hello"


def test_history_to_prompt_with_history():
    """Test prompt building includes history with correct role labels."""
    history = [HumanMessage(content="q1"), AIMessage(content="a1")]
    result = AnthropicAgentBackend._langchain_history_to_prompt("q2", history)
    assert "User: q1" in result
    assert "Assistant: a1" in result
    assert result.endswith("User: q2")


def test_history_to_prompt_preserves_order():
    """Test prompt building preserves message order."""
    history = [
        HumanMessage(content="first"),
        AIMessage(content="second"),
        HumanMessage(content="third"),
        AIMessage(content="fourth"),
    ]
    result = AnthropicAgentBackend._langchain_history_to_prompt("fifth", history)
    parts = result.split("\n\n")
    assert len(parts) == 5
    assert parts[0] == "User: first"
    assert parts[4] == "User: fifth"


@pytest.mark.asyncio
async def test_openai_backend_not_implemented(_sample_run_config):
    """Test that the OpenAI backend raises NotImplementedError."""
    backend = OpenAIAgentBackend()
    with pytest.raises(NotImplementedError, match="OpenAI Agents SDK"):
        async for _ in backend.run(_sample_run_config):
            pass


@pytest.mark.asyncio
async def test_google_adk_backend_not_implemented(_sample_run_config):
    """Test that the Google ADK backend raises NotImplementedError."""
    backend = GoogleADKBackend()
    with pytest.raises(NotImplementedError, match="Google ADK"):
        async for _ in backend.run(_sample_run_config):
            pass


def test_orchestrator_uses_default_provider_model():
    """Test that the orchestrator resolves defaults from config."""
    orchestrator = AgentSDKOrchestrator(
        backend_type=constants.AGENT_SDK_BACKEND_ANTHROPIC
    )
    assert orchestrator.provider == "p1"
    assert orchestrator.model == "m1"


def test_orchestrator_uses_provided_provider_model():
    """Test that explicit provider/model override defaults."""
    orchestrator = AgentSDKOrchestrator(
        provider="p1",
        model="m2",
        backend_type=constants.AGENT_SDK_BACKEND_ANTHROPIC,
    )
    assert orchestrator.provider == "p1"
    assert orchestrator.model == "m2"


def test_orchestrator_caches_provider_url():
    """Test that provider_url is resolved at init time."""
    orchestrator = AgentSDKOrchestrator(
        backend_type=constants.AGENT_SDK_BACKEND_ANTHROPIC
    )
    assert orchestrator._provider_url is not None
    assert "url1" in orchestrator._provider_url


def test_orchestrator_resolves_system_prompt_from_config():
    """Test that the system prompt is resolved from config."""
    orchestrator = AgentSDKOrchestrator(
        backend_type=constants.AGENT_SDK_BACKEND_ANTHROPIC
    )
    assert orchestrator._system_prompt == config.ols_config.system_prompt


def test_agent_sdk_backend_is_abstract():
    """Test that AgentSDKBackend cannot be instantiated directly."""
    with pytest.raises(TypeError):
        AgentSDKBackend()


def test_backend_run_config_is_frozen():
    """Test that BackendRunConfig is immutable after creation."""
    cfg = BackendRunConfig(
        query="q",
        system_prompt="s",
        history=[],
        model="m",
        credentials=None,
        provider_url=None,
        max_tokens=100,
        max_iterations=5,
    )
    with pytest.raises(AttributeError):
        cfg.query = "changed"


def test_backend_run_config_stores_all_fields():
    """Test that BackendRunConfig preserves all provided values."""
    history = [HumanMessage(content="hi")]
    cfg = BackendRunConfig(
        query="q",
        system_prompt="sys",
        history=history,
        model="gpt",
        credentials="key",
        provider_url="https://api",
        max_tokens=200,
        max_iterations=10,
    )
    assert cfg.query == "q"
    assert cfg.system_prompt == "sys"
    assert cfg.history is history
    assert cfg.model == "gpt"
    assert cfg.credentials == "key"
    assert cfg.provider_url == "https://api"
    assert cfg.max_tokens == 200
    assert cfg.max_iterations == 10
