# temporal/converter.py
from typing import Any, Dict, List, Optional
import json
from pydantic import BaseModel
import inspect

from praisonaiagents import Agent, Task
from praisonaiagents.main import TaskOutput

def serialize_agent(agent: Agent) -> Dict[str, Any]:
    """Serialize an Agent into a JSON-serializable config dictionary."""
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
        "llm": agent.llm,
        "tools": tools,
    }
    
    # Optional kwargs
    if hasattr(agent, "verbose"): config["verbose"] = agent.verbose
    if hasattr(agent, "max_retries"): config["max_retries"] = agent.max_retries
    
    return config

def deserialize_agent(config: Dict[str, Any], tool_registry: Optional[Dict[str, Any]] = None) -> Agent:
    """Reconstruct an Agent from a config dictionary."""
    config_copy = config.copy()
    
    tools_refs = config_copy.pop("tools", [])
    resolved_tools = []
    
    if tool_registry and tools_refs:
        for ref in tools_refs:
            if ref in tool_registry:
                resolved_tools.append(tool_registry[ref])
            else:
                resolved_tools.append(ref) # fallback to string
                
    agent = Agent(tools=resolved_tools, **config_copy)
    return agent

def serialize_task(task: Task) -> Dict[str, Any]:
    """Serialize a Task into a JSON-serializable config dictionary."""
    config = {
        "name": task.name,
        "description": task.description,
        "expected_output": task.expected_output,
        "status": task.status,
    }
    
    if task.agent:
        config["agent_name"] = task.agent.name
        
    return config

def deserialize_task(config: Dict[str, Any], agents_map: Optional[Dict[str, Agent]] = None) -> Task:
    """Reconstruct a Task from a config dictionary."""
    config_copy = config.copy()
    agent_name = config_copy.pop("agent_name", None)
    
    agent = None
    if agent_name and agents_map and agent_name in agents_map:
        agent = agents_map[agent_name]
        
    task = Task(agent=agent, **config_copy)
    return task

def serialize_task_output(output: TaskOutput) -> Dict[str, Any]:
    """Serialize a TaskOutput into a JSON-serializable dictionary."""
    return {
        "description": output.description,
        "summary": output.summary,
        "raw": output.raw,
        "json_dict": output.json_dict,
        "agent": output.agent,
        "output_format": output.output_format,
    }

def deserialize_task_output(data: Dict[str, Any]) -> TaskOutput:
    """Reconstruct a TaskOutput from a serialized dictionary."""
    return TaskOutput(**data)
