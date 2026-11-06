from google.adk.agents import SequentialAgent

from agents.atvos_agent import (
    campaign_description_agent,
    campaign_orchestrator,
    campaign_prompt_agent,
    root_agent,
)


def test_root_agent_is_the_campaign_orchestrator() -> None:
    assert isinstance(root_agent, SequentialAgent)
    assert root_agent is campaign_orchestrator


def test_orchestrator_has_both_specialized_agents() -> None:
    assert [agent.name for agent in root_agent.sub_agents] == [
        "campaign_prompt_agent",
        "campaign_description_agent",
    ]


def test_prompt_agent_writes_the_prompt_state() -> None:
    assert campaign_prompt_agent.output_key == "campaign_prompt"
    assert isinstance(campaign_prompt_agent.instruction, str)
    assert "compliance" in campaign_prompt_agent.instruction.lower()
    assert "No inventes requisitos" in campaign_prompt_agent.instruction


def test_description_agent_reads_the_generated_prompt() -> None:
    assert campaign_description_agent.output_key == "campaign_description"
    assert isinstance(campaign_description_agent.instruction, str)
    assert "{campaign_prompt}" in campaign_description_agent.instruction
    assert "compliance" in campaign_description_agent.instruction.lower()
