import asyncio
from typing import Dict, Any, List, Optional
import logging

from praisonaiagents.execution.protocols import ExecutionBackendProtocol
from praisonaiagents.temporal.config import TemporalConfig

logger = logging.getLogger(__name__)

class TemporalExecutionBackend(ExecutionBackendProtocol):
    _client = None
    _worker_task = None

    def __init__(self, config: Optional[TemporalConfig] = None):
        self.config = config or TemporalConfig()
        self._client = None
        self._worker_task = None

    async def _get_client(self):
        if self._client is None:
            try:
                from temporalio.client import Client, TLSConfig
            except ImportError as e:
                raise ImportError(
                    "The 'temporal' backend requires the 'temporalio' package. "
                    "Install with: pip install 'praisonaiagents[temporal]'"
                ) from e
            
            tls_config = None
            if self.config.tls:
                if self.config.tls_cert_path and self.config.tls_key_path:
                    tls_config = TLSConfig(
                        client_cert=self.config.tls_cert_path,
                        client_private_key=self.config.tls_key_path,
                    )
                else:
                    tls_config = TLSConfig()
            
            self._client = await Client.connect(
                self.config.address,
                namespace=self.config.namespace,
                tls=tls_config,
            )
            
            if self.config.start_worker:
                from praisonaiagents.temporal.worker import start_worker_if_needed
                self._worker_task = await start_worker_if_needed(self._client, self.config)
                
        return self._client

    async def execute_team(
        self,
        agents: List[Any],
        tasks: Dict[str, Any],
        process_mode: str,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        from praisonaiagents.temporal.converter import serialize_agent, serialize_task
        from praisonaiagents.temporal.workflows import AgentTeamWorkflow, TeamInput
        import uuid
        
        client = await self._get_client()
        
        serialized_agents = []
        for a in agents:
            try:
                serialized_agents.append(serialize_agent(a))
            except Exception as e:
                logger.error(f"Failed to serialize agent {getattr(a, 'name', 'unknown')}: {e}")
                raise ValueError(f"Agent serialization failed: {e}") from e
        
        serialized_tasks = {}
        for t_id, t in tasks.items():
            try:
                serialized_tasks[t_id] = serialize_task(t)
            except Exception as e:
                logger.error(f"Failed to serialize task {t_id}: {e}")
                raise ValueError(f"Task serialization failed: {e}") from e
        
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

    async def close(self) -> None:
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
        
        self._client = None
