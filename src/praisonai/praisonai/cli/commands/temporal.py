import asyncio
import click
import logging

logger = logging.getLogger(__name__)

@click.group()
def temporal():
    pass

@temporal.command()
@click.option('--address', default='localhost:7233', help='Temporal server address')
@click.option('--namespace', 'namespace_', default='default', help='Temporal namespace')
@click.option('--task-queue', default='praisonai-agents', help='Task queue name')
@click.option('--concurrency', default=4, help='Max concurrent activities')
def worker(address, namespace_, task_queue, concurrency):
    """Start a Temporal worker for PraisonAI agents."""
    try:
        from temporalio.client import Client
        from temporalio.worker import Worker
        from praisonaiagents.temporal.workflows import AgentTeamWorkflow
        from praisonaiagents.temporal.activities import execute_agent_task
    except ImportError:
        click.echo("Error: temporalio not installed. Run: pip install 'praisonaiagents[temporal]'", err=True)
        raise SystemExit(1)
    
    async def run_worker():
        client = await Client.connect(address, namespace=namespace_)
        worker = Worker(
            client,
            task_queue=task_queue,
            workflows=[AgentTeamWorkflow],
            activities=[execute_agent_task],
            max_concurrent_activities=concurrency
        )
        click.echo(f"Starting Temporal worker on {address} (namespace={namespace_}, queue={task_queue})")
        await worker.run()
    
    asyncio.run(run_worker())

@temporal.command()
@click.argument('workflow_id')
@click.option('--address', default='localhost:7233', help='Temporal server address')
@click.option('--namespace', 'namespace_', default='default', help='Temporal namespace')
def status(workflow_id, address, namespace_):
    """Get status of a running workflow."""
    try:
        from temporalio.client import Client
    except ImportError:
        click.echo("Error: temporalio not installed. Run: pip install 'praisonaiagents[temporal]'", err=True)
        raise SystemExit(1)
    
    async def get_status():
        client = await Client.connect(address, namespace=namespace_)
        handle = client.get_workflow_handle(workflow_id)
        desc = await handle.describe()
        click.echo(f"Workflow ID: {desc.id}")
        click.echo(f"Status: {desc.status}")
        click.echo(f"Task Queue: {desc.task_queue}")
    
    asyncio.run(get_status())

@temporal.command()
@click.argument('workflow_id')
@click.argument('task_id')
@click.option('--approved/--rejected', default=True, help='Approval decision')
@click.option('--address', default='localhost:7233', help='Temporal server address')
@click.option('--namespace', 'namespace_', default='default', help='Temporal namespace')
def approve(workflow_id, task_id, approved, address, namespace_):
    """Send approval signal to a workflow."""
    try:
        from temporalio.client import Client
    except ImportError:
        click.echo("Error: temporalio not installed. Run: pip install 'praisonaiagents[temporal]'", err=True)
        raise SystemExit(1)
    
    async def send_approval():
        client = await Client.connect(address, namespace=namespace_)
        handle = client.get_workflow_handle(workflow_id)
        await handle.signal("approve_task", task_id, approved)
        click.echo(f"Sent approval signal: task={task_id} approved={approved}")
    
    asyncio.run(send_approval())

@temporal.command()
@click.argument('workflow_id')
@click.option('--reason', default='User requested', help='Cancellation reason')
@click.option('--address', default='localhost:7233', help='Temporal server address')
@click.option('--namespace', 'namespace_', default='default', help='Temporal namespace')
def cancel(workflow_id, reason, address, namespace_):
    """Cancel a running workflow."""
    try:
        from temporalio.client import Client
    except ImportError:
        click.echo("Error: temporalio not installed. Run: pip install 'praisonaiagents[temporal]'", err=True)
        raise SystemExit(1)
    
    async def cancel_workflow():
        client = await Client.connect(address, namespace=namespace_)
        handle = client.get_workflow_handle(workflow_id)
        await handle.cancel()
        click.echo(f"Cancelled workflow: {workflow_id}")
    
    asyncio.run(cancel_workflow())
