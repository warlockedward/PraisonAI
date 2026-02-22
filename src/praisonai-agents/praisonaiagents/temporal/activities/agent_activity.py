from typing import Dict, Any, Optional
from praisonaiagents.temporal.activities.models import AgentActivityInput
from praisonaiagents import TaskOutput

def _get_activity_defn():
    try:
        from temporalio import activity
        return activity
    except ImportError as e:
        raise ImportError(
            "The 'temporal' backend requires the 'temporalio' package. "
            "Install with: pip install 'praisonaiagents[temporal]'"
        ) from e

activity = _get_activity_defn()

@activity.defn
async def execute_agent_task(input_data: AgentActivityInput) -> Dict[str, Any]:
    from praisonaiagents.temporal.converter import (
        deserialize_agent, deserialize_task, serialize_task_output
    )
    
    agent = None
    if input_data.agent_config:
        try:
            agent = deserialize_agent(input_data.agent_config)
        except Exception as e:
            return serialize_task_output(TaskOutput(
                description="Agent deserialization failed",
                raw=f"Error: {e}",
                agent="error"
            ))
    
    try:
        task = deserialize_task(input_data.task_config)
    except Exception as e:
        return serialize_task_output(TaskOutput(
            description="Task deserialization failed",
            raw=f"Error: {e}",
            agent=agent.name if agent else "unknown"
        ))
    
    if agent:
        task.agent = agent
        
    if input_data.context_data:
        if not task.context:
            task.context = []
        task.context.append(input_data.context_data)
    
    try:
        if agent:
            result = await agent.aexecute_task(task)
        else:
            from praisonaiagents import Agent
            default_agent = Agent(name="default_agent")
            result = await default_agent.aexecute_task(task)
    except Exception as e:
        return serialize_task_output(TaskOutput(
            description=task.description or "Task execution failed",
            raw=f"Error: {e}",
            agent=agent.name if agent else "default_agent"
        ))
        
    if isinstance(result, TaskOutput):
        return serialize_task_output(result)
    elif isinstance(result, str):
        output = TaskOutput(description=task.description or "", raw=result, agent=agent.name if agent else "default_agent")
        return serialize_task_output(output)
    elif hasattr(result, "raw"):
        output = TaskOutput(description=task.description or "", raw=str(result.raw), agent=agent.name if agent else "default_agent")
        return serialize_task_output(output)
    else:
        output = TaskOutput(description=task.description or "", raw=str(result), agent=agent.name if agent else "default_agent")
        return serialize_task_output(output)
