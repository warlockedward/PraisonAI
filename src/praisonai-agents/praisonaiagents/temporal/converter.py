from typing import Any, Dict, List, Optional
import logging

from praisonaiagents import Agent, Task
from praisonaiagents.main import TaskOutput

logger = logging.getLogger(__name__)

def serialize_agent(agent: Agent) -> Dict[str, Any]:
    tools = []
    if agent.tools:
        for tool in agent.tools:
            if callable(tool) and hasattr(tool, '__name__'):
                tools.append(tool.__name__)
            elif isinstance(tool, str):
                tools.append(tool)
            else:
                tools.append(str(tool))
                
    config = {
        "name": agent.name,
        "role": getattr(agent, "role", None),
        "goal": getattr(agent, "goal", None),
        "backstory": getattr(agent, "backstory", None),
        "instructions": getattr(agent, "instructions", None),
        "llm": getattr(agent, "llm", None),
        "tools": tools,
    }
    
    if hasattr(agent, "verbose"): config["verbose"] = agent.verbose
    if hasattr(agent, "max_retries"): config["max_retries"] = agent.max_retries
    
    return config

def deserialize_agent(config: Dict[str, Any], tool_registry: Optional[Dict[str, Any]] = None) -> Agent:
    config_copy = config.copy()
    
    tools_refs = config_copy.pop("tools", [])
    resolved_tools = []
    
    if tool_registry and tools_refs:
        for ref in tools_refs:
            if ref in tool_registry:
                resolved_tools.append(tool_registry[ref])
            else:
                resolved_tools.append(ref)
    
    try:
        agent = Agent(tools=resolved_tools, **config_copy)
        return agent
    except Exception as e:
        logger.error(f"Failed to deserialize agent: {e}")
        raise ValueError(f"Agent deserialization failed: {e}") from e

def serialize_task(task: Task) -> Dict[str, Any]:
    config = {
        "name": task.name,
        "description": task.description,
        "expected_output": getattr(task, "expected_output", None),
        "status": getattr(task, "status", "not_started"),
    }
    
    if task.agent:
        config["agent_name"] = task.agent.name
        
    return config

def deserialize_task(config: Dict[str, Any], agents_map: Optional[Dict[str, Agent]] = None) -> Task:
    config_copy = config.copy()
    agent_name = config_copy.pop("agent_name", None)
    
    agent = None
    if agent_name and agents_map and agent_name in agents_map:
        agent = agents_map[agent_name]
    
    try:
        task = Task(agent=agent, **config_copy)
        return task
    except Exception as e:
        logger.error(f"Failed to deserialize task: {e}")
        raise ValueError(f"Task deserialization failed: {e}") from e

def serialize_task_output(output: TaskOutput) -> Dict[str, Any]:
    return {
        "description": getattr(output, "description", None),
        "summary": getattr(output, "summary", None),
        "raw": getattr(output, "raw", None),
        "json_dict": getattr(output, "json_dict", None),
        "agent": getattr(output, "agent", None),
        "output_format": getattr(output, "output_format", None),
    }

def deserialize_task_output(data: Dict[str, Any]) -> TaskOutput:
    try:
        return TaskOutput(**data)
    except Exception as e:
        logger.error(f"Failed to deserialize TaskOutput: {e}")
        return TaskOutput(description="Deserialization failed", raw=str(data), agent="unknown")
