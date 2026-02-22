import asyncio
from typing import Dict, Any, List, Optional
import logging
from temporalio.client import Client

from praisonaiagents.execution.protocols import ExecutionBackendProtocol
from praisonaiagents.temporal.config import TemporalConfig
from praisonaiagents.temporal.converter import serialize_agent, serialize_task
from praisonaiagents.temporal.workflows import AgentTeamWorkflow, TeamInput
from praisonaiagents.temporal.worker import start_worker_if_needed

logger = logging.getLogger(__name__)

class TemporalExecutionBackend(ExecutionBackendProtocol):
    """Execution backend that orchestrates agents using Temporal workflows."""

    def __init__(self, config: Optional[TemporalConfig] = None):
        self.config = config or TemporalConfig()
        self._client: Optional[Client] = None
        self._worker_task: Optional[asyncio.Task] = None

    async def _get_client(self) -> Client:
        if not self._client:
            self._client = await Client.connect(
                self.config.address,
                namespace=self.config.namespace
            )
            
            if self.config.start_worker:
                self._worker_task = await start_worker_if_needed(self._client, self.config)
                
        return self._client

    async def execute_team(
        self,
        agents: List[Any],
        tasks: Dict[str, Any],
        process_mode: str,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        client = await self._get_client()
        
        serialized_agents = [serialize_agent(a) for a in agents]
        
        serialized_tasks = {
            t_id: serialize_task(t) 
            for t_id, t in tasks.items()
        }
        
        import uuid
        workflow_id = f"praisonai-team-{uuid.uuid4()}"
        
        team_input = TeamInput(
            agents_config=serialized_agents,
            tasks_config=serialized_tasks,
            process_mode=process_mode,
            config=config.get("team_config", {})
        )
        
        logger.info(f"Starting Temporal workflow {workflow_id} for AgentTeam")
        
        result = await client.execute_workflow(
            AgentTeamWorkflow.run,
            team_input,
            id=workflow_id,
            task_queue=self.config.task_queue,
            execution_timeout=self.config.workflow_execution_timeout,
        )
        
        return result

    async def execute_task(
        self,
        task: Any,
        agent: Any,
        context: str,
    ) -> Any:
        raise NotImplementedError("Direct task execution not yet implemented via Temporal")

    async def execute_workflow(
        self,
        steps: List[Any],
        input_data: str,
        variables: Dict[str, Any],
    ) -> Dict[str, Any]:
        raise NotImplementedError("Workflow pattern mapping not yet implemented via Temporal")

    async def get_status(self, execution_id: str) -> Dict[str, Any]:
        raise NotImplementedError()

    async def send_signal(self, execution_id: str, signal: str, data: Any) -> None:
        raise NotImplementedError()

    async def cancel(self, execution_id: str) -> None:
        raise NotImplementedError()
