from typing import Dict, Any, Optional
from temporalio import activity

from praisonaiagents.temporal.converter import deserialize_agent, deserialize_task, serialize_task_output
from praisonaiagents.temporal.activities.models import AgentActivityInput
from praisonaiagents import TaskOutput

@activity.defn
async def execute_agent_task(input_data: AgentActivityInput) -> Dict[str, Any]:
    """Execute a single agent task in a Temporal activity."""
    agent = None
    if input_data.agent_config:
        agent = deserialize_agent(input_data.agent_config)
        
    task = deserialize_task(input_data.task_config)
    if agent:
        task.agent = agent
        
    if input_data.context_data:
        if not task.context:
            task.context = []
        task.context.append(input_data.context_data)
        
    if agent:
        result = await agent.aexecute_task(task)
    else:
        from praisonaiagents import Agent
        default_agent = Agent(name="default_agent")
        result = await default_agent.aexecute_task(task)
        
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
