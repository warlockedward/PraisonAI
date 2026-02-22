import pytest
from praisonaiagents.temporal.activities.models import AgentActivityInput
from praisonaiagents.temporal.activities.agent_activity import execute_agent_task
from praisonaiagents.temporal.converter import serialize_agent, serialize_task
from praisonaiagents import Agent, Task

@pytest.mark.asyncio
async def test_execute_agent_task_activity():
    agent = Agent(name="TestAgent", instructions="Return exactly 'Activity Output'")
    task = Task(name="test_task", description="Run this", agent=agent)
    
    input_data = AgentActivityInput(
        agent_config=serialize_agent(agent),
        task_config=serialize_task(task),
        context_data="Test Context"
    )
    
    class MockAgent:
        async def aexecute_task(self, task):
            from praisonaiagents import TaskOutput
            return TaskOutput(description="mock desc", raw="Activity Output", agent="TestAgent")
            
    import praisonaiagents.temporal.activities.agent_activity as activity_module
    original_deserialize = activity_module.deserialize_agent
    activity_module.deserialize_agent = lambda x: MockAgent()
    
    try:
        result = await execute_agent_task(input_data)
        assert result["raw"] == "Activity Output"
        assert result["agent"] == "TestAgent"
    finally:
        activity_module.deserialize_agent = original_deserialize
