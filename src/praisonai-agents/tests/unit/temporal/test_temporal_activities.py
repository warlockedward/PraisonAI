import pytest
from unittest.mock import patch, AsyncMock
from praisonaiagents.temporal.activities.models import AgentActivityInput
from praisonaiagents.temporal.converter import serialize_agent, serialize_task
from praisonaiagents import Agent, Task

@pytest.mark.asyncio
async def test_execute_agent_task_activity():
    try:
        from praisonaiagents.temporal.activities.agent_activity import execute_agent_task
    except ImportError as e:
        if "temporalio" in str(e):
            pytest.skip("temporalio not installed")
        raise
    
    agent = Agent(name="TestAgent", instructions="Return exactly 'Activity Output'")
    task = Task(name="test_task", description="Run this", agent=agent)
    
    input_data = AgentActivityInput(
        agent_config=serialize_agent(agent),
        task_config=serialize_task(task),
        context_data="Test Context"
    )
    
    class MockAgent:
        name = "TestAgent"
        async def aexecute_task(self, task):
            from praisonaiagents import TaskOutput
            return TaskOutput(description="mock desc", raw="Activity Output", agent="TestAgent")
    
    mock_agent = MockAgent()
    
    with patch(
        'praisonaiagents.temporal.converter.deserialize_agent',
        return_value=mock_agent
    ):
        result = await execute_agent_task(input_data)
        assert result["raw"] == "Activity Output"
        assert result["agent"] == "TestAgent"
