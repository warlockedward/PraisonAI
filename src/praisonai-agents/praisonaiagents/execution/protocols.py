# execution/protocols.py
from typing import Protocol, Any, Dict, List, Optional, runtime_checkable

@runtime_checkable
class ExecutionBackendProtocol(Protocol):
    """Protocol for execution backends (local, temporal, etc.)"""

    async def execute_team(
        self,
        agents: List[Any],
        tasks: Dict[str, Any],
        process_mode: str,  # "sequential" | "parallel" | "hierarchical"
        config: Dict[str, Any],
    ) -> Dict[str, Any]: ...

    async def execute_task(
        self,
        task: Any,
        agent: Any,
        context: str,
    ) -> Any: ...

    async def execute_workflow(
        self,
        steps: List[Any],
        input_data: str,
        variables: Dict[str, Any],
    ) -> Dict[str, Any]: ...

    async def get_status(self, execution_id: str) -> Dict[str, Any]: ...
    async def send_signal(self, execution_id: str, signal: str, data: Any) -> None: ...
    async def cancel(self, execution_id: str) -> None: ...
