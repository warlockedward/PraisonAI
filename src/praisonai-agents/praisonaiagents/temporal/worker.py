import asyncio
import logging
from typing import Optional
from temporalio.client import Client
from temporalio.worker import Worker

from praisonaiagents.temporal.config import TemporalConfig
from praisonaiagents.temporal.workflows import AgentTeamWorkflow
from praisonaiagents.temporal.activities import execute_agent_task

logger = logging.getLogger(__name__)

async def start_worker_if_needed(client: Client, config: TemporalConfig) -> Optional[asyncio.Task]:
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
