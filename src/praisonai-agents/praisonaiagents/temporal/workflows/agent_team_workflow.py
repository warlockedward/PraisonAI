from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import logging

try:
    from temporalio import workflow
    TEMPORAL_AVAILABLE = True
except ImportError:
    TEMPORAL_AVAILABLE = False
    workflow = None

logger = logging.getLogger(__name__)

@dataclass
class TeamInput:
    agents_config: List[Dict[str, Any]]
    tasks_config: Dict[str, Dict[str, Any]]
    process_mode: str
    config: Dict[str, Any]

if TEMPORAL_AVAILABLE:
    with workflow.unsafe.imports_passed_through():
        from praisonaiagents.temporal.activities.models import AgentActivityInput
        from praisonaiagents import TaskOutput

    @workflow.defn
    class AgentTeamWorkflow:
        def __init__(self):
            self._approval_status: Dict[str, Optional[bool]] = {}
            self._pending_approval: bool = False
            self._approval_task_id: Optional[str] = None
        
        @workflow.run
        async def run(self, input_data: TeamInput) -> Dict[str, Any]:
            from temporalio.common import RetryPolicy
            from datetime import timedelta
            
            valid_modes = ("sequential", "parallel", "hierarchical")
            if input_data.process_mode not in valid_modes:
                raise ValueError(f"Unknown process mode: {input_data.process_mode}. Valid modes: {valid_modes}")
            
            if input_data.process_mode == "sequential":
                return await self._run_sequential(input_data)
            elif input_data.process_mode == "parallel":
                return await self._run_parallel(input_data)
            elif input_data.process_mode == "hierarchical":
                return await self._run_hierarchical(input_data)
        
        @workflow.signal
        async def approve_task(self, task_id: str, approved: bool) -> None:
            self._approval_status[task_id] = approved
            self._pending_approval = False
        
        @workflow.signal
        async def request_approval(self, task_id: str) -> None:
            self._approval_task_id = task_id
            self._approval_status[task_id] = None
            self._pending_approval = True
        
        async def _wait_for_approval(self, task_id: str, timeout_seconds: int = 86400) -> bool:
            from datetime import timedelta
            try:
                await workflow.wait_condition(
                    lambda: self._approval_status.get(task_id) is not None,
                    timeout=timedelta(seconds=timeout_seconds)
                )
            except Exception:
                return False
            return self._approval_status.get(task_id, False)
                
        async def _run_sequential(self, input_data: TeamInput) -> Dict[str, Any]:
            from datetime import timedelta
            from temporalio.common import RetryPolicy
            
            results = {}
            for task_id, task_config in input_data.tasks_config.items():
                
                agent_config = None
                agent_name = task_config.get("agent_name")
                if agent_name:
                    for ac in input_data.agents_config:
                        if ac.get("name") == agent_name:
                            agent_config = ac
                            break
                            
                activity_input = AgentActivityInput(
                    task_config=task_config,
                    agent_config=agent_config,
                    context_data=None
                )
                
                max_retries = agent_config.get("max_retries", 3) if agent_config else 3
                
                result_dict = await workflow.execute_activity(
                    "execute_agent_task",
                    activity_input,
                    schedule_to_close_timeout=timedelta(minutes=30),
                    retry_policy=RetryPolicy(
                        maximum_attempts=max_retries,
                        initial_interval=timedelta(seconds=2),
                        backoff_coefficient=2.0,
                        maximum_interval=timedelta(minutes=5),
                    )
                )
                
                results[task_id] = result_dict
                
            return {
                "task_status": {task_id: "completed" for task_id in results.keys()},
                "task_results": results
            }
            
        async def _run_parallel(self, input_data: TeamInput) -> Dict[str, Any]:
            from datetime import timedelta
            from temporalio.common import RetryPolicy
            import asyncio
            
            async def execute_single_task(task_id: str, task_config: Dict[str, Any]) -> tuple:
                agent_config = None
                agent_name = task_config.get("agent_name")
                if agent_name:
                    for ac in input_data.agents_config:
                        if ac.get("name") == agent_name:
                            agent_config = ac
                            break
                            
                activity_input = AgentActivityInput(
                    task_config=task_config,
                    agent_config=agent_config,
                    context_data=None
                )
                
                max_retries = agent_config.get("max_retries", 3) if agent_config else 3
                
                result_dict = await workflow.execute_activity(
                    "execute_agent_task",
                    activity_input,
                    schedule_to_close_timeout=timedelta(minutes=30),
                    retry_policy=RetryPolicy(
                        maximum_attempts=max_retries,
                        initial_interval=timedelta(seconds=2),
                        backoff_coefficient=2.0,
                        maximum_interval=timedelta(minutes=5),
                    )
                )
                return task_id, result_dict
            
            tasks = [
                execute_single_task(task_id, task_config)
                for task_id, task_config in input_data.tasks_config.items()
            ]
            
            results_list = await asyncio.gather(*tasks)
            results = dict(results_list)
            
            return {
                "task_status": {task_id: "completed" for task_id in results.keys()},
                "task_results": results
            }
            
        async def _run_hierarchical(self, input_data: TeamInput) -> Dict[str, Any]:
            raise NotImplementedError("Hierarchical process mode not yet implemented for Temporal backend")
else:
    class AgentTeamWorkflow:
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "The 'temporal' backend requires the 'temporalio' package. "
                "Install with: pip install 'praisonaiagents[temporal]'"
            )
