# execution/local_backend.py
from typing import Any, Dict, List
from .protocols import ExecutionBackendProtocol

class LocalExecutionBackend(ExecutionBackendProtocol):
    
    async def execute_team(
        self,
        agents: List[Any],
        tasks: Dict[str, Any],
        process_mode: str,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        team = config.get("team")
        if not team:
            raise ValueError("LocalExecutionBackend requires 'team' in config")
        
        await team.arun_all_tasks()
        return {}

    async def execute_task(
        self,
        task: Any,
        agent: Any,
        context: str,
    ) -> Any:
        raise NotImplementedError("Stub for protocol compliance")

    async def execute_workflow(
        self,
        steps: List[Any],
        input_data: str,
        variables: Dict[str, Any],
    ) -> Dict[str, Any]:
        raise NotImplementedError("Stub for protocol compliance")

    async def get_status(self, execution_id: str) -> Dict[str, Any]:
        return {"status": "completed"}

    async def send_signal(self, execution_id: str, signal: str, data: Any) -> None:
        pass

    async def cancel(self, execution_id: str) -> None:
        pass
