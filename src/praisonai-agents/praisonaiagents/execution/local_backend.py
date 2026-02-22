from typing import Any, Dict, List
import logging
from .protocols import ExecutionBackendProtocol

logger = logging.getLogger(__name__)

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
        
        results = {
            "task_status": team.get_all_tasks_status() if hasattr(team, 'get_all_tasks_status') else {},
            "task_results": {}
        }
        
        if hasattr(team, 'tasks') and hasattr(team, 'get_task_result'):
            for task_id in team.tasks:
                result = team.get_task_result(task_id)
                if result:
                    results["task_results"][task_id] = {
                        "raw": getattr(result, 'raw', str(result)),
                        "agent": getattr(result, 'agent', None),
                    }
        
        return results

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
