import pytest
import asyncio
from datetime import timedelta

@pytest.fixture
async def temporal_client():
    try:
        from temporalio.client import Client
    except ImportError:
        pytest.skip("temporalio not installed")
    
    try:
        client = await Client.connect("localhost:7233", namespace="default")
        return client
    except Exception as e:
        pytest.skip(f"Could not connect to Temporal server: {e}")

@pytest.mark.asyncio
@pytest.mark.integration
async def test_e2e_sequential_workflow(temporal_client):
    from temporalio.worker import Worker
    from praisonaiagents.temporal.workflows import AgentTeamWorkflow, TeamInput
    from praisonaiagents.temporal.activities import execute_agent_task
    from temporalio import activity
    from praisonaiagents.temporal.activities.models import AgentActivityInput
    from praisonaiagents import TaskOutput
    from praisonaiagents.temporal.converter import serialize_task_output
    
    @activity.defn(name="execute_agent_task")
    async def mock_execute(input_data: AgentActivityInput) -> dict:
        return serialize_task_output(TaskOutput(
            description=input_data.task_config.get("description", ""),
            raw=f"E2E Result for {input_data.task_config['name']}",
            agent=input_data.agent_config.get("name") if input_data.agent_config else "default"
        ))
    
    async with Worker(
        temporal_client,
        task_queue="e2e-test-queue",
        workflows=[AgentTeamWorkflow],
        activities=[mock_execute],
    ):
        input_data = TeamInput(
            agents_config=[{"name": "TestAgent"}],
            tasks_config={
                "task1": {"name": "task1", "description": "First task", "agent_name": "TestAgent"},
                "task2": {"name": "task2", "description": "Second task", "agent_name": "TestAgent"}
            },
            process_mode="sequential",
            config={}
        )
        
        result = await temporal_client.execute_workflow(
            AgentTeamWorkflow.run,
            input_data,
            id="e2e-sequential-test",
            task_queue="e2e-test-queue",
            execution_timeout=timedelta(minutes=5)
        )
        
        assert result["task_status"]["task1"] == "completed"
        assert result["task_status"]["task2"] == "completed"
        assert "E2E Result" in result["task_results"]["task1"]["raw"]

@pytest.mark.asyncio
@pytest.mark.integration
async def test_e2e_parallel_workflow(temporal_client):
    from temporalio.worker import Worker
    from praisonaiagents.temporal.workflows import AgentTeamWorkflow, TeamInput
    from praisonaiagents.temporal.activities import execute_agent_task
    from temporalio import activity
    from praisonaiagents.temporal.activities.models import AgentActivityInput
    from praisonaiagents import TaskOutput
    from praisonaiagents.temporal.converter import serialize_task_output
    
    @activity.defn(name="execute_agent_task")
    async def mock_execute(input_data: AgentActivityInput) -> dict:
        await asyncio.sleep(0.1)
        return serialize_task_output(TaskOutput(
            description=input_data.task_config.get("description", ""),
            raw=f"Parallel: {input_data.task_config['name']}",
            agent="TestAgent"
        ))
    
    async with Worker(
        temporal_client,
        task_queue="e2e-parallel-queue",
        workflows=[AgentTeamWorkflow],
        activities=[mock_execute],
    ):
        input_data = TeamInput(
            agents_config=[{"name": "TestAgent"}],
            tasks_config={
                "p1": {"name": "p1", "description": "Parallel 1"},
                "p2": {"name": "p2", "description": "Parallel 2"},
                "p3": {"name": "p3", "description": "Parallel 3"}
            },
            process_mode="parallel",
            config={}
        )
        
        result = await temporal_client.execute_workflow(
            AgentTeamWorkflow.run,
            input_data,
            id="e2e-parallel-test",
            task_queue="e2e-parallel-queue",
            execution_timeout=timedelta(minutes=5)
        )
        
        assert len(result["task_results"]) == 3
        for task_id in ["p1", "p2", "p3"]:
            assert result["task_status"][task_id] == "completed"
