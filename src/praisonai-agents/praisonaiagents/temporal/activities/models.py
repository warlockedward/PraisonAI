from dataclasses import dataclass
from typing import Dict, Any, List, Optional

@dataclass
class AgentActivityInput:
    task_config: Dict[str, Any]
    agent_config: Optional[Dict[str, Any]] = None
    context_data: Optional[str] = None

@dataclass
class ManagerDecisionInput:
    """Input for manager decision activity."""
    tasks_status: Dict[str, Dict[str, Any]]
    agents_config: List[Dict[str, Any]]
    manager_llm: Optional[str] = None
    manager_config: Optional[Dict[str, Any]] = None
