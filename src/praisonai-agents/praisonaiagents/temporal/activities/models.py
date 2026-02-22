from dataclasses import dataclass
from typing import Dict, Any, List, Optional

@dataclass
class AgentActivityInput:
    task_config: Dict[str, Any]
    agent_config: Optional[Dict[str, Any]] = None
    context_data: Optional[str] = None
