from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from temporalio import workflow
import logging

with workflow.unsafe.imports_passed_through():
    from praisonaiagents.temporal.activities.models import AgentActivityInput
    from praisonaiagents.temporal.converter import serialize_task_output
    from praisonaiagents import TaskOutput

logger = logging.getLogger(__name__)

@dataclass
class WorkflowPatternInput:
    pattern_type: str  # "route", "loop", "repeat", "parallel"
    pattern_config: Dict[str, Any]
    agents_config: List[Dict[str, Any]]
    context: Dict[str, Any]

@workflow.defn
class WorkflowPatternWorkflow:
    @workflow.run
    async def run(self, input_data: WorkflowPatternInput) -> Dict[str, Any]:
        from datetime import timedelta
        from temporalio.common import RetryPolicy
        
        if input_data.pattern_type == "route":
            return await self._run_route(input_data)
        elif input_data.pattern_type == "loop":
            return await self._run_loop(input_data)
        elif input_data.pattern_type == "repeat":
            return await self._run_repeat(input_data)
        elif input_data.pattern_type == "parallel":
            return await self._run_parallel(input_data)
        else:
            raise ValueError(f"Unknown pattern type: {input_data.pattern_type}")

    async def _run_route(self, input_data: WorkflowPatternInput) -> Dict[str, Any]:
        from datetime import timedelta
        from temporalio.common import RetryPolicy
        
        route_config = input_data.pattern_config
        condition_agent = route_config.get("condition_agent")
        
        if condition_agent:
            activity_input = AgentActivityInput(
                task_config={"name": "route_condition", "description": route_config.get("condition", "")},
                agent_config=condition_agent,
                context_data=None
            )
            condition_result = await workflow.execute_activity(
                "execute_agent_task",
                activity_input,
                schedule_to_close_timeout=timedelta(minutes=10),
                retry_policy=RetryPolicy(maximum_attempts=3)
            )
            decision = condition_result.get("raw", "").lower()
            
            for route_key, route_agents in route_config.get("routes", {}).items():
                if route_key.lower() in decision:
                    selected_agents = route_agents
                    break
            else:
                selected_agents = route_config.get("default", [])
        else:
            selected_agents = route_config.get("default", [])
        
        results = {}
        for agent_config in selected_agents:
            activity_input = AgentActivityInput(
                task_config={"name": f"route_task_{len(results)}", "description": route_config.get("task", "")},
                agent_config=agent_config,
                context_data=None
            )
            result = await workflow.execute_activity(
                "execute_agent_task",
                activity_input,
                schedule_to_close_timeout=timedelta(minutes=30),
                retry_policy=RetryPolicy(maximum_attempts=3)
            )
            results[f"route_{len(results)}"] = result
        
        return {"pattern": "route", "results": results}

    async def _run_loop(self, input_data: WorkflowPatternInput) -> Dict[str, Any]:
        from datetime import timedelta
        from temporalio.common import RetryPolicy
        
        loop_config = input_data.pattern_config
        items = loop_config.get("items", [])
        task_template = loop_config.get("task_template", {})
        
        results = []
        for idx, item in enumerate(items):
            task_config = dict(task_template)
            task_config["description"] = task_config.get("description", "").replace("{{item}}", str(item))
            
            activity_input = AgentActivityInput(
                task_config=task_config,
                agent_config=loop_config.get("agent"),
                context_data=str(item)
            )
            result = await workflow.execute_activity(
                "execute_agent_task",
                activity_input,
                schedule_to_close_timeout=timedelta(minutes=30),
                retry_policy=RetryPolicy(maximum_attempts=3)
            )
            results.append(result)
        
        return {"pattern": "loop", "results": results, "count": len(results)}

    async def _run_repeat(self, input_data: WorkflowPatternInput) -> Dict[str, Any]:
        from datetime import timedelta
        from temporalio.common import RetryPolicy
        
        repeat_config = input_data.pattern_config
        max_iterations = repeat_config.get("max_iterations", 3)
        evaluator_agent = repeat_config.get("evaluator")
        generator_agent = repeat_config.get("generator")
        task_config = repeat_config.get("task", {})
        
        current_result = None
        iterations = 0
        
        while iterations < max_iterations:
            if current_result is None:
                agent_config = generator_agent
            else:
                agent_config = generator_agent
            
            activity_input = AgentActivityInput(
                task_config=task_config,
                agent_config=agent_config,
                context_data=str(current_result) if current_result else None
            )
            gen_result = await workflow.execute_activity(
                "execute_agent_task",
                activity_input,
                schedule_to_close_timeout=timedelta(minutes=30),
                retry_policy=RetryPolicy(maximum_attempts=3)
            )
            
            if evaluator_agent:
                eval_input = AgentActivityInput(
                    task_config={"name": "evaluation", "description": f"Evaluate: {gen_result.get('raw', '')}"},
                    agent_config=evaluator_agent,
                    context_data=None
                )
                eval_result = await workflow.execute_activity(
                    "execute_agent_task",
                    eval_input,
                    schedule_to_close_timeout=timedelta(minutes=10),
                    retry_policy=RetryPolicy(maximum_attempts=3)
                )
                
                if "approved" in eval_result.get("raw", "").lower():
                    current_result = gen_result
                    break
            
            current_result = gen_result
            iterations += 1
        
        return {"pattern": "repeat", "result": current_result, "iterations": iterations}

    async def _run_parallel(self, input_data: WorkflowPatternInput) -> Dict[str, Any]:
        import asyncio
        from datetime import timedelta
        from temporalio.common import RetryPolicy
        
        parallel_config = input_data.pattern_config
        tasks = parallel_config.get("tasks", [])
        
        async def execute_task(idx: int, task_cfg: Dict[str, Any]):
            activity_input = AgentActivityInput(
                task_config=task_cfg,
                agent_config=task_cfg.get("agent"),
                context_data=None
            )
            return idx, await workflow.execute_activity(
                "execute_agent_task",
                activity_input,
                schedule_to_close_timeout=timedelta(minutes=30),
                retry_policy=RetryPolicy(maximum_attempts=3)
            )
        
        coros = [execute_task(i, t) for i, t in enumerate(tasks)]
        results_list = await asyncio.gather(*coros)
        results = dict(results_list)
        
        return {"pattern": "parallel", "results": results}
