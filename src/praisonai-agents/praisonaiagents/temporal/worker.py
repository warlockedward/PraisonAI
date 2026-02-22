import asyncio
import logging
from typing import Optional, TYPE_CHECKING

from praisonaiagents.temporal.config import TemporalConfig

if TYPE_CHECKING:
    from temporalio.client import Client

logger = logging.getLogger(__name__)

async def start_worker_if_needed(client: "Client", config: TemporalConfig) -> Optional[asyncio.Task]:
    try:
        from temporalio.worker import Worker
    except ImportError as e:
        raise ImportError(
            "The 'temporal' backend requires the 'temporalio' package. "
            "Install with: pip install 'praisonaiagents[temporal]'"
        ) from e
    
    from praisonaiagents.temporal.workflows import AgentTeamWorkflow
    from praisonaiagents.temporal.activities import execute_agent_task
    
    logger.info(f"Starting embedded Temporal worker on task queue '{config.task_queue}'")
    
    worker = Worker(
        client,
        task_queue=config.task_queue,
        workflows=[AgentTeamWorkflow],
        activities=[execute_agent_task],
        max_concurrent_activities=config.worker_count,
    )
    
    task = asyncio.create_task(worker.run())
    await asyncio.sleep(0.1)
    
    return task
