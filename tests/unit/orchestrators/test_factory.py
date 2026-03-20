"""Unit tests for the orchestrator factory."""

import pytest

from ols import config, constants

# needs to be setup before importing modules that trigger auth dependency
config.ols_config.authentication_config.module = "k8s"
from ols.src.orchestrators.agent_sdk import AgentSDKOrchestrator  # noqa: E402
from ols.src.orchestrators.factory import create_orchestrator  # noqa: E402
from ols.src.query_helpers.docs_summarizer import DocsSummarizer  # noqa: E402
from tests.mock_classes.mock_llm_loader import mock_llm_loader  # noqa: E402


@pytest.fixture(scope="function", autouse=True)
def _setup():
    """Load a valid config for tests."""
    config.reload_from_yaml_file("tests/config/valid_config_without_mcp.yaml")


def test_default_returns_docs_summarizer():
    """Test that the factory returns DocsSummarizer by default."""
    orchestrator = create_orchestrator(llm_loader=mock_llm_loader(None))
    assert isinstance(orchestrator, DocsSummarizer)


def test_langchain_type_returns_docs_summarizer():
    """Test that orchestrator_type='langchain' returns DocsSummarizer."""
    config.ols_config.orchestrator_type = constants.ORCHESTRATOR_LANGCHAIN
    orchestrator = create_orchestrator(llm_loader=mock_llm_loader(None))
    assert isinstance(orchestrator, DocsSummarizer)


def test_agent_sdk_type_returns_agent_sdk_orchestrator():
    """Test that orchestrator_type='agent_sdk' returns AgentSDKOrchestrator."""
    config.ols_config.orchestrator_type = constants.ORCHESTRATOR_AGENT_SDK
    config.ols_config.agent_sdk_backend = constants.AGENT_SDK_BACKEND_ANTHROPIC
    orchestrator = create_orchestrator()
    assert isinstance(orchestrator, AgentSDKOrchestrator)


def test_agent_sdk_with_openai_backend():
    """Test that agent_sdk with openai backend works."""
    config.ols_config.orchestrator_type = constants.ORCHESTRATOR_AGENT_SDK
    config.ols_config.agent_sdk_backend = constants.AGENT_SDK_BACKEND_OPENAI
    orchestrator = create_orchestrator()
    assert isinstance(orchestrator, AgentSDKOrchestrator)


def test_agent_sdk_with_google_adk_backend():
    """Test that agent_sdk with google_adk backend works."""
    config.ols_config.orchestrator_type = constants.ORCHESTRATOR_AGENT_SDK
    config.ols_config.agent_sdk_backend = constants.AGENT_SDK_BACKEND_GOOGLE_ADK
    orchestrator = create_orchestrator()
    assert isinstance(orchestrator, AgentSDKOrchestrator)


def test_factory_passes_params_to_docs_summarizer():
    """Test that the factory forwards parameters correctly."""
    orchestrator = create_orchestrator(
        provider="p1",
        model="m1",
        system_prompt="test prompt",
        streaming=True,
        llm_loader=mock_llm_loader(None),
    )
    assert isinstance(orchestrator, DocsSummarizer)
    assert orchestrator.provider == "p1"
    assert orchestrator.model == "m1"


def test_factory_passes_mode_to_agent_sdk():
    """Test that the factory passes mode to AgentSDKOrchestrator."""
    config.ols_config.orchestrator_type = constants.ORCHESTRATOR_AGENT_SDK
    config.ols_config.agent_sdk_backend = constants.AGENT_SDK_BACKEND_ANTHROPIC
    orchestrator = create_orchestrator(mode=constants.MODE_DESIGN)
    assert isinstance(orchestrator, AgentSDKOrchestrator)
    assert orchestrator.mode == constants.MODE_DESIGN


def test_factory_defaults_mode_to_qa():
    """Test that the factory defaults to qa mode when none specified."""
    config.ols_config.orchestrator_type = constants.ORCHESTRATOR_AGENT_SDK
    config.ols_config.agent_sdk_backend = constants.AGENT_SDK_BACKEND_ANTHROPIC
    orchestrator = create_orchestrator()
    assert isinstance(orchestrator, AgentSDKOrchestrator)
    assert orchestrator.mode == constants.MODE_QA


def test_factory_passes_remediate_mode():
    """Test that the factory passes remediate mode correctly."""
    config.ols_config.orchestrator_type = constants.ORCHESTRATOR_AGENT_SDK
    config.ols_config.agent_sdk_backend = constants.AGENT_SDK_BACKEND_ANTHROPIC
    orchestrator = create_orchestrator(mode=constants.MODE_REMEDIATE)
    assert isinstance(orchestrator, AgentSDKOrchestrator)
    assert orchestrator.mode == constants.MODE_REMEDIATE
