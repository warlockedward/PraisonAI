import pytest
from praisonaiagents import Agent, AgentTeam

def test_agent_team_accepts_execution_param():
    agent = Agent(name="test", instructions="Be helpful")
    team = AgentTeam(agents=[agent], execution="local")
    assert team._execution_backend_config == "local"

def test_agent_team_default_execution_is_none():
    agent = Agent(name="test", instructions="Be helpful")
    team = AgentTeam(agents=[agent])
    assert getattr(team, "_execution_backend_config", None) is None
