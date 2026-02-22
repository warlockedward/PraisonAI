import pytest
from unittest.mock import AsyncMock, patch
from datetime import timedelta
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from praisonaiagents.temporal.workflows.agent_team_workflow import AgentTeamWorkflow, TeamInput

@pytest.mark.asyncio
async def test_agent_team_workflow_parallel():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        from temporalio import activity
        from praisonaiagents.temporal.activities.models import AgentActivityInput
        from praisonaiagents import TaskOutput
        from praisonaiagents.temporal.converter import serialize_task_output
        
        @activity.defn(name="execute_agent_task")
        async def mock_execute_agent_task(input_data: AgentActivityInput) -> dict:
            return serialize_task_output(TaskOutput(
                description=input_data.task_config.get("description", ""),
                raw=f"Parallel {input_data.task_config['name']}",
                agent=input_data.agent_config.get("name") if input_data.agent_config else "default"
            ))

        async with Worker(
            env.client,
            task_queue="test-queue-parallel",
            workflows=[AgentTeamWorkflow],
            activities=[mock_execute_agent_task],
        ):
            input_data = TeamInput(
                agents_config=[{"name": "Agent1"}],
                tasks_config={
                    "task1": {"name": "task1", "description": "d1", "agent_name": "Agent1"},
                    "task2": {"name": "task2", "description": "d2", "agent_name": "Agent1"}
                },
                process_mode="parallel",
                config={}
            )
            
            result = await env.client.execute_workflow(
                AgentTeamWorkflow.run,
                input_data,
                id="test-workflow-par",
                task_queue="test-queue-parallel",
            )
            
            assert "task_status" in result
            assert result["task_status"]["task1"] == "completed"
            assert result["task_results"]["task1"]["raw"] == "Parallel task1"
            assert result["task_results"]["task2"]["raw"] == "Parallel task2"
