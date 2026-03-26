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
from ols.src.orchestrators.prompts import (
    ANALYSIS_SYSTEM_PROMPT,
    EXECUTION_SYSTEM_PROMPT,
    VERIFICATION_SYSTEM_PROMPT,
    build_escalation_prompt,
)
from ols.src.orchestrators.schemas import MODE_OUTPUT_SCHEMAS
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


# --- Mode tests ---


def test_backend_run_config_default_mode():
    """Test that BackendRunConfig defaults to qa mode."""
    cfg = BackendRunConfig(
        query="q",
        system_prompt="s",
        history=[],
        model="m",
        credentials=None,
        provider_url=None,
        max_tokens=100,
        max_iterations=3,
    )
    assert cfg.mode == constants.MODE_QA


def test_backend_run_config_default_tools():
    """Test that BackendRunConfig gets default tools when none provided."""
    cfg = BackendRunConfig(
        query="q",
        system_prompt="s",
        history=[],
        model="m",
        credentials=None,
        provider_url=None,
        max_tokens=100,
        max_iterations=3,
    )
    assert cfg.tools == constants.AGENT_SDK_DEFAULT_TOOLS


def test_backend_run_config_custom_tools():
    """Test that BackendRunConfig accepts custom tool list."""
    custom_tools = ["Bash", "Read"]
    cfg = BackendRunConfig(
        query="q",
        system_prompt="s",
        history=[],
        model="m",
        credentials=None,
        provider_url=None,
        max_tokens=100,
        max_iterations=3,
        tools=custom_tools,
    )
    assert cfg.tools == custom_tools


def test_backend_run_config_explicit_mode():
    """Test that BackendRunConfig accepts explicit mode."""
    cfg = BackendRunConfig(
        query="q",
        system_prompt="s",
        history=[],
        model="m",
        credentials=None,
        provider_url=None,
        max_tokens=100,
        max_iterations=3,
        mode=constants.MODE_DESIGN,
    )
    assert cfg.mode == constants.MODE_DESIGN


def test_orchestrator_default_mode_is_qa():
    """Test that orchestrator defaults to qa mode."""
    orchestrator = AgentSDKOrchestrator(
        backend_type=constants.AGENT_SDK_BACKEND_ANTHROPIC,
    )
    assert orchestrator.mode == constants.MODE_QA


def test_orchestrator_design_mode_uses_analysis_prompt():
    """Test that design mode selects the analysis system prompt."""
    orchestrator = AgentSDKOrchestrator(
        backend_type=constants.AGENT_SDK_BACKEND_ANTHROPIC,
        mode=constants.MODE_DESIGN,
    )
    assert orchestrator._system_prompt == ANALYSIS_SYSTEM_PROMPT


def test_orchestrator_remediate_mode_uses_analysis_prompt():
    """Test that remediate mode selects the analysis system prompt."""
    orchestrator = AgentSDKOrchestrator(
        backend_type=constants.AGENT_SDK_BACKEND_ANTHROPIC,
        mode=constants.MODE_REMEDIATE,
    )
    assert orchestrator._system_prompt == ANALYSIS_SYSTEM_PROMPT


def test_orchestrator_qa_mode_uses_config_prompt():
    """Test that qa mode falls back to config system prompt."""
    orchestrator = AgentSDKOrchestrator(
        backend_type=constants.AGENT_SDK_BACKEND_ANTHROPIC,
        mode=constants.MODE_QA,
    )
    assert orchestrator._system_prompt == config.ols_config.system_prompt


def test_orchestrator_design_mode_tools():
    """Test that design mode gets web-enabled tools."""
    orchestrator = AgentSDKOrchestrator(
        backend_type=constants.AGENT_SDK_BACKEND_ANTHROPIC,
        mode=constants.MODE_DESIGN,
    )
    assert orchestrator._tools == constants.AGENT_SDK_DESIGN_TOOLS


def test_orchestrator_remediate_mode_tools():
    """Test that remediate mode gets read-only tools."""
    orchestrator = AgentSDKOrchestrator(
        backend_type=constants.AGENT_SDK_BACKEND_ANTHROPIC,
        mode=constants.MODE_REMEDIATE,
    )
    assert orchestrator._tools == constants.AGENT_SDK_READONLY_TOOLS


def test_orchestrator_deploy_mode_tools():
    """Test that deploy mode gets write tools."""
    orchestrator = AgentSDKOrchestrator(
        backend_type=constants.AGENT_SDK_BACKEND_ANTHROPIC,
        mode=constants.MODE_DEPLOY,
    )
    assert orchestrator._tools == constants.AGENT_SDK_WRITE_TOOLS


def test_orchestrator_qa_mode_tools():
    """Test that qa mode gets default tools."""
    orchestrator = AgentSDKOrchestrator(
        backend_type=constants.AGENT_SDK_BACKEND_ANTHROPIC,
        mode=constants.MODE_QA,
    )
    assert orchestrator._tools == constants.AGENT_SDK_DEFAULT_TOOLS


def test_orchestrator_system_prompt_override_takes_precedence():
    """Test that explicit system_prompt override beats mode prompt."""
    try:
        config.dev_config.enable_system_prompt_override = True
        orchestrator = AgentSDKOrchestrator(
            backend_type=constants.AGENT_SDK_BACKEND_ANTHROPIC,
            mode=constants.MODE_DESIGN,
            system_prompt="my custom prompt",
        )
        assert orchestrator._system_prompt == "my custom prompt"
    finally:
        config.dev_config.enable_system_prompt_override = False


def test_orchestrator_system_prompt_override_ignored_when_disabled():
    """Test that system_prompt override is ignored when config disables it."""
    config.dev_config.enable_system_prompt_override = False
    orchestrator = AgentSDKOrchestrator(
        backend_type=constants.AGENT_SDK_BACKEND_ANTHROPIC,
        mode=constants.MODE_DESIGN,
        system_prompt="my custom prompt",
    )
    assert orchestrator._system_prompt == ANALYSIS_SYSTEM_PROMPT


def test_orchestrator_deploy_mode_uses_execution_prompt():
    """Test that deploy mode selects the execution system prompt."""
    orchestrator = AgentSDKOrchestrator(
        backend_type=constants.AGENT_SDK_BACKEND_ANTHROPIC,
        mode=constants.MODE_DEPLOY,
    )
    assert orchestrator._system_prompt == EXECUTION_SYSTEM_PROMPT


def test_orchestrator_monitor_mode_uses_analysis_prompt():
    """Test that monitor mode selects the analysis system prompt."""
    orchestrator = AgentSDKOrchestrator(
        backend_type=constants.AGENT_SDK_BACKEND_ANTHROPIC,
        mode=constants.MODE_MONITOR,
    )
    assert orchestrator._system_prompt == ANALYSIS_SYSTEM_PROMPT


def test_orchestrator_escalate_mode_uses_escalation_prompt():
    """Test that escalate mode builds the escalation prompt with target repo."""
    orchestrator = AgentSDKOrchestrator(
        backend_type=constants.AGENT_SDK_BACKEND_ANTHROPIC,
        mode=constants.MODE_ESCALATE,
    )
    expected = build_escalation_prompt(constants.DEFAULT_ESCALATION_TARGET_REPO)
    assert orchestrator._system_prompt == expected
    assert constants.DEFAULT_ESCALATION_TARGET_REPO in orchestrator._system_prompt


def test_orchestrator_monitor_mode_tools():
    """Test that monitor mode gets monitor (readonly) tools."""
    orchestrator = AgentSDKOrchestrator(
        backend_type=constants.AGENT_SDK_BACKEND_ANTHROPIC,
        mode=constants.MODE_MONITOR,
    )
    assert orchestrator._tools == constants.AGENT_SDK_MONITOR_TOOLS


def test_orchestrator_escalate_mode_tools():
    """Test that escalate mode gets escalation tools with web access."""
    orchestrator = AgentSDKOrchestrator(
        backend_type=constants.AGENT_SDK_BACKEND_ANTHROPIC,
        mode=constants.MODE_ESCALATE,
    )
    assert orchestrator._tools == constants.AGENT_SDK_ESCALATION_TOOLS


def test_orchestrator_verify_mode_tools():
    """Test that verify mode gets readonly tools."""
    orchestrator = AgentSDKOrchestrator(
        backend_type=constants.AGENT_SDK_BACKEND_ANTHROPIC,
        mode=constants.MODE_VERIFY,
    )
    assert orchestrator._tools == constants.AGENT_SDK_VERIFY_TOOLS


def test_mode_verify_in_supported_modes():
    """Test that MODE_VERIFY is included in SUPPORTED_MODES."""
    assert constants.MODE_VERIFY in constants.SUPPORTED_MODES


def test_mode_monitor_in_supported_modes():
    """Test that MODE_MONITOR is included in SUPPORTED_MODES."""
    assert constants.MODE_MONITOR in constants.SUPPORTED_MODES


def test_orchestrator_verify_mode_uses_verification_prompt():
    """Test that verify mode selects the verification system prompt."""
    orchestrator = AgentSDKOrchestrator(
        backend_type=constants.AGENT_SDK_BACKEND_ANTHROPIC,
        mode=constants.MODE_VERIFY,
    )
    assert orchestrator._system_prompt == VERIFICATION_SYSTEM_PROMPT


def test_analysis_modes_share_same_prompt():
    """Test that design, remediate, and monitor all use the analysis prompt."""
    prompts = {}
    for mode in (constants.MODE_DESIGN, constants.MODE_REMEDIATE, constants.MODE_MONITOR):
        orchestrator = AgentSDKOrchestrator(
            backend_type=constants.AGENT_SDK_BACKEND_ANTHROPIC,
            mode=mode,
        )
        prompts[mode] = orchestrator._system_prompt
    assert prompts[constants.MODE_DESIGN] is prompts[constants.MODE_REMEDIATE]
    assert prompts[constants.MODE_DESIGN] is prompts[constants.MODE_MONITOR]


def test_analysis_modes_share_same_schema():
    """Test that design, remediate, and monitor share the analysis output schema."""
    schemas = {}
    for mode in (constants.MODE_DESIGN, constants.MODE_REMEDIATE, constants.MODE_MONITOR):
        orchestrator = AgentSDKOrchestrator(
            backend_type=constants.AGENT_SDK_BACKEND_ANTHROPIC,
            mode=mode,
        )
        schemas[mode] = orchestrator._output_format["schema"]
    assert schemas[constants.MODE_DESIGN] is schemas[constants.MODE_REMEDIATE]
    assert schemas[constants.MODE_DESIGN] is schemas[constants.MODE_MONITOR]


def test_all_modes_have_prompt_mapping():
    """Test that every non-QA mode has a dedicated system prompt."""
    modes_with_prompts = {
        constants.MODE_DESIGN,
        constants.MODE_DEPLOY,
        constants.MODE_MONITOR,
        constants.MODE_REMEDIATE,
        constants.MODE_ESCALATE,
        constants.MODE_VERIFY,
    }
    for mode in modes_with_prompts:
        orchestrator = AgentSDKOrchestrator(
            backend_type=constants.AGENT_SDK_BACKEND_ANTHROPIC,
            mode=mode,
        )
        # Mode-specific prompts should NOT equal the default config prompt
        assert orchestrator._system_prompt != config.ols_config.system_prompt


# --- Schema tests ---


def test_orchestrator_design_mode_has_output_schema():
    """Test that design mode resolves the analysis output schema."""
    orchestrator = AgentSDKOrchestrator(
        backend_type=constants.AGENT_SDK_BACKEND_ANTHROPIC,
        mode=constants.MODE_DESIGN,
    )
    assert orchestrator._output_format is not None
    assert orchestrator._output_format["type"] == "json_schema"
    assert "analysis" in orchestrator._output_format["schema"]["required"]


def test_orchestrator_deploy_mode_has_output_schema():
    """Test that deploy mode resolves an output schema."""
    orchestrator = AgentSDKOrchestrator(
        backend_type=constants.AGENT_SDK_BACKEND_ANTHROPIC,
        mode=constants.MODE_DEPLOY,
    )
    assert orchestrator._output_format is not None
    assert orchestrator._output_format["type"] == "json_schema"
    assert "result" in orchestrator._output_format["schema"]["required"]


def test_orchestrator_monitor_mode_has_output_schema():
    """Test that monitor mode resolves the analysis output schema."""
    orchestrator = AgentSDKOrchestrator(
        backend_type=constants.AGENT_SDK_BACKEND_ANTHROPIC,
        mode=constants.MODE_MONITOR,
    )
    assert orchestrator._output_format is not None
    assert orchestrator._output_format["type"] == "json_schema"
    assert "analysis" in orchestrator._output_format["schema"]["required"]


def test_orchestrator_escalate_mode_has_output_schema():
    """Test that escalate mode resolves an output schema."""
    orchestrator = AgentSDKOrchestrator(
        backend_type=constants.AGENT_SDK_BACKEND_ANTHROPIC,
        mode=constants.MODE_ESCALATE,
    )
    assert orchestrator._output_format is not None
    assert orchestrator._output_format["type"] == "json_schema"
    assert "report" in orchestrator._output_format["schema"]["required"]


def test_orchestrator_verify_mode_has_output_schema():
    """Test that verify mode resolves a verification output schema."""
    orchestrator = AgentSDKOrchestrator(
        backend_type=constants.AGENT_SDK_BACKEND_ANTHROPIC,
        mode=constants.MODE_VERIFY,
    )
    assert orchestrator._output_format is not None
    assert orchestrator._output_format["type"] == "json_schema"
    assert "verification" in orchestrator._output_format["schema"]["required"]


def test_orchestrator_remediate_mode_has_output_schema():
    """Test that remediate mode resolves the analysis output schema."""
    orchestrator = AgentSDKOrchestrator(
        backend_type=constants.AGENT_SDK_BACKEND_ANTHROPIC,
        mode=constants.MODE_REMEDIATE,
    )
    assert orchestrator._output_format is not None
    assert orchestrator._output_format["type"] == "json_schema"
    assert "analysis" in orchestrator._output_format["schema"]["required"]


def test_orchestrator_qa_mode_has_no_output_schema():
    """Test that qa mode does not set an output schema."""
    orchestrator = AgentSDKOrchestrator(
        backend_type=constants.AGENT_SDK_BACKEND_ANTHROPIC,
        mode=constants.MODE_QA,
    )
    assert orchestrator._output_format is None


def test_backend_run_config_output_format_default_none():
    """Test that BackendRunConfig defaults output_format to None."""
    cfg = BackendRunConfig(
        query="q",
        system_prompt="s",
        history=[],
        model="m",
        credentials=None,
        provider_url=None,
        max_tokens=100,
        max_iterations=3,
    )
    assert cfg.output_format is None


def test_backend_run_config_accepts_output_format():
    """Test that BackendRunConfig stores a custom output_format."""
    schema = {"type": "json_schema", "schema": {"type": "object"}}
    cfg = BackendRunConfig(
        query="q",
        system_prompt="s",
        history=[],
        model="m",
        credentials=None,
        provider_url=None,
        max_tokens=100,
        max_iterations=3,
        output_format=schema,
    )
    assert cfg.output_format == schema
