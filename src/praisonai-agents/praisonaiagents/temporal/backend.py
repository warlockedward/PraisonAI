import asyncio
from typing import Dict, Any, List, Optional
import logging

from praisonaiagents.execution.protocols import ExecutionBackendProtocol
from praisonaiagents.temporal.config import TemporalConfig

logger = logging.getLogger(__name__)

class TemporalExecutionBackend(ExecutionBackendProtocol):
    _client = None
    _worker_task = None
    _health_check_task = None

    def __init__(self, config: Optional[TemporalConfig] = None):
        self.config = config or TemporalConfig()
        self._client = None
        self._worker_task = None
        self._health_check_task = None

    async def _connect_with_retry(self) -> Any:
        """Connect to Temporal server with retry logic."""
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
        
        last_error = None
        for attempt in range(self.config.connect_retries):
            try:
                client = await asyncio.wait_for(
                    Client.connect(
                        self.config.address,
                        namespace=self.config.namespace,
                        tls=tls_config,
                    ),
                    timeout=self.config.connect_timeout.total_seconds()
                )
                logger.info(f"Connected to Temporal server at {self.config.address}")
                return client
            except asyncio.TimeoutError as e:
                last_error = e
                logger.warning(f"Connection attempt {attempt + 1} timed out after {self.config.connect_timeout.total_seconds()}s")
            except Exception as e:
                last_error = e
                logger.warning(f"Connection attempt {attempt + 1} failed: {e}")
            
            if attempt < self.config.connect_retries - 1:
                await asyncio.sleep(self.config.connect_retry_delay.total_seconds())
        
        raise ConnectionError(
            f"Failed to connect to Temporal server at {self.config.address} "
            f"after {self.config.connect_retries} attempts: {last_error}"
        )

    async def _health_check_loop(self) -> None:
        """Background task for periodic health checks."""
        while True:
            try:
                await asyncio.sleep(self.config.health_check_interval.total_seconds())
                if self._client is not None:
                    await self._client.service_client.health_check()
                    logger.debug("Temporal health check passed")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Temporal health check failed: {e}")

    async def is_healthy(self) -> bool:
        """Check if the Temporal connection is healthy."""
        if self._client is None:
            return False
        try:
            await self._client.service_client.health_check()
            return True
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False

    async def _get_client(self):
        if self._client is None:
            self._client = await self._connect_with_retry()
            
            if self.config.start_worker:
                from praisonaiagents.temporal.worker import start_worker_if_needed
                self._worker_task = await start_worker_if_needed(self._client, self.config)
            
            # Start health check background task
            self._health_check_task = asyncio.create_task(self._health_check_loop())
                
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
        """Get the status of a workflow execution."""
        client = await self._get_client()
        handle = client.get_workflow_handle(execution_id)
        
        try:
            description = await handle.describe()
            return {
                "execution_id": execution_id,
                "status": description.status.name if hasattr(description, 'status') else "UNKNOWN",
                "start_time": description.start_time if hasattr(description, 'start_time') else None,
                "close_time": description.close_time if hasattr(description, 'close_time') else None,
                "history_length": description.history_length if hasattr(description, 'history_length') else None,
            }
        except Exception as e:
            logger.error(f"Failed to get status for workflow {execution_id}: {e}")
            raise

    async def send_signal(self, execution_id: str, signal: str, data: Any) -> None:
        """Send a signal to a running workflow."""
        client = await self._get_client()
        handle = client.get_workflow_handle(execution_id)
        
        try:
            await handle.signal(signal, data)
            logger.info(f"Sent signal '{signal}' to workflow {execution_id}")
        except Exception as e:
            logger.error(f"Failed to send signal '{signal}' to workflow {execution_id}: {e}")
            raise

    async def cancel(self, execution_id: str) -> None:
        """Cancel a running workflow."""
        client = await self._get_client()
        handle = client.get_workflow_handle(execution_id)
        
        try:
            await handle.cancel()
            logger.info(f"Cancelled workflow {execution_id}")
        except Exception as e:
            logger.error(f"Failed to cancel workflow {execution_id}: {e}")
            raise

    async def query(self, execution_id: str, query: str, *args) -> Any:
        """Query a workflow for current state."""
        client = await self._get_client()
        handle = client.get_workflow_handle(execution_id)
        
        try:
            result = await handle.query(query, *args)
            return result
        except Exception as e:
            logger.error(f"Failed to query workflow {execution_id}: {e}")
            raise

    async def terminate(self, execution_id: str, reason: str = "") -> None:
        """Terminate a workflow immediately."""
        client = await self._get_client()
        handle = client.get_workflow_handle(execution_id)
        
        try:
            await handle.terminate(reason=reason)
            logger.info(f"Terminated workflow {execution_id}: {reason}")
        except Exception as e:
            logger.error(f"Failed to terminate workflow {execution_id}: {e}")
            raise

    async def close(self) -> None:
        """Close the Temporal client and cleanup resources."""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None
        
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
        
        self._client = None
