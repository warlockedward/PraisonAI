from typing import Dict, Any, Optional
from praisonaiagents.temporal.activities.models import AgentActivityInput, ManagerDecisionInput
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

@activity.defn
async def manager_decide_next_task(input_data: ManagerDecisionInput) -> Dict[str, Any]:
    """
    Manager activity that decides which task to execute next.
    
    Returns:
        Dict with 'task_id', 'agent_name', and 'action' (execute/stop)
    """
    from praisonaiagents import Agent
    import json
    
    manager_llm = input_data.manager_llm or "gpt-4o-mini"
    
    manager = Agent(
        name="Manager",
        role="Project manager",
        goal="Manage the entire flow of tasks and delegate them to the right agent",
        instructions="Expert project manager to coordinate tasks among agents",
        llm=manager_llm,
    )
    
    tasks_summary = []
    for task_id, task_info in input_data.tasks_status.items():
        task_entry = {
            "task_id": task_id,
            "name": task_info.get("name", task_id),
            "description": task_info.get("description", ""),
            "status": task_info.get("status", "not started"),
            "agent": task_info.get("agent_name", "No agent")
        }
        tasks_summary.append(task_entry)
    
    agent_names = [a.get("name", "unknown") for a in input_data.agents_config]
    
    prompt = f"""Here is the current status of all tasks:
{json.dumps(tasks_summary, indent=2)}

Available agents: {', '.join(agent_names)}

Decide the next task to execute. Provide a JSON with this exact structure:
{{
   "task_id": "<task_id string>",
   "agent_name": "<agent name>",
   "action": "<execute or stop>"
}}

Rules:
- Select a task that is NOT completed
- Choose the most appropriate agent for the task
- Use "stop" action when all tasks are completed or no more work is needed
- Always return valid JSON
"""
    
    try:
        response = await manager.astart(prompt)
        
        response_text = response if isinstance(response, str) else str(response)
        
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            json_str = response_text[json_start:json_end]
            decision = json.loads(json_str)
            return decision
        else:
            return {"task_id": "", "agent_name": "", "action": "stop"}
            
    except Exception as e:
        return {
            "task_id": "",
            "agent_name": "", 
            "action": "stop",
            "error": str(e)
        }
