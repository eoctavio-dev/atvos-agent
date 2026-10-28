from google.adk.agents import Agent

from agents.atvos_agent import root_agent


def test_root_agent_is_an_adk_agent() -> None:
    assert isinstance(root_agent, Agent)


def test_root_agent_configuration() -> None:
    assert root_agent.name == "atvos_agent"
    assert root_agent.model == "gemini-2.5-flash"


def test_root_agent_describes_google_cloud_scope() -> None:
    assert "Google Cloud" in root_agent.description
    assert "Google Cloud" in root_agent.instruction


def test_root_agent_instructions_require_grounded_answers() -> None:
    assert "No inventes resultados" in root_agent.instruction
