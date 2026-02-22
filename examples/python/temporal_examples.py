"""
Temporal Execution Backend Examples

This module demonstrates how to use Temporal as an execution backend
for durable, scalable agent orchestration in PraisonAI.
"""

import asyncio
from datetime import timedelta

# ============================================================================
# Example 1: Basic Temporal Execution
# ============================================================================

async def basic_temporal_execution():
    from praisonaiagents import Agent, AgentTeam, Task

    researcher = Agent(
        name="researcher",
        instructions="You are a research assistant. Provide thorough analysis."
    )
    
    writer = Agent(
        name="writer", 
        instructions="You are a content writer. Create engaging summaries."
    )

    t1 = Task(
        name="research",
        description="Research the benefits of AI agents in enterprise",
        agent=researcher
    )
    
    t2 = Task(
        name="write",
        description="Write a summary based on the research",
        agent=writer
    )

    team = AgentTeam(
        agents=[researcher, writer],
        tasks=[t1, t2],
        execution="temporal"
    )

    result = team.start()
    print(f"Results: {result}")
    return result


# ============================================================================
# Example 2: Full Configuration
# ============================================================================

async def full_configuration():
    from praisonaiagents import Agent, AgentTeam, Task
    from praisonaiagents.temporal import TemporalConfig

    config = TemporalConfig(
        address="localhost:7233",
        namespace="default",
        task_queue="praisonai-agents",
        workflow_execution_timeout=timedelta(hours=2),
        default_activity_timeout=timedelta(minutes=15),
        default_retry_policy={
            "maximum_attempts": 3,
            "initial_interval": 2,
            "backoff_coefficient": 2.0,
            "maximum_interval": 60,
        },
        start_worker=True,
        worker_count=4
    )

    agent = Agent(name="assistant", instructions="Be helpful")
    task = Task(name="help", description="Help the user", agent=agent)

    team = AgentTeam(
        agents=[agent],
        tasks=[task],
        execution=config
    )

    result = team.start()
    return result


# ============================================================================
# Example 3: Parallel Execution
# ============================================================================

async def parallel_execution():
    from praisonaiagents import Agent, AgentTeam, Task

    agents = [
        Agent(name=f"agent_{i}", instructions=f"You are agent {i}")
        for i in range(3)
    ]

    tasks = [
        Task(
            name=f"task_{i}",
            description=f"Process item {i}",
            agent=agents[i % 3]
        )
        for i in range(6)
    ]

    team = AgentTeam(
        agents=agents,
        tasks=tasks,
        process="parallel",
        execution="temporal"
    )

    result = team.start()
    print(f"Parallel results: {result}")
    return result


# ============================================================================
# Example 4: Human Approval Workflow
# ============================================================================

async def human_approval_workflow():
    from praisonaiagents import Agent, AgentTeam, Task
    from praisonaiagents.temporal import TemporalConfig
    from temporalio.client import Client

    config = TemporalConfig(
        start_worker=False
    )

    reviewer = Agent(
        name="reviewer",
        instructions="Review content and decide if it needs approval"
    )

    task = Task(
        name="review",
        description="Review this important document",
        agent=reviewer
    )

    team = AgentTeam(
        agents=[reviewer],
        tasks=[task],
        execution=config
    )

    workflow_task = asyncio.create_task(asyncio.to_thread(team.start))

    await asyncio.sleep(2)

    client = await Client.connect("localhost:7233")
    
    handle = client.get_workflow_handle_for(
        team._execution_backend._client._last_workflow_id
    )
    
    await handle.signal("approve_task", "review", True)
    
    result = await workflow_task
    print(f"Approved result: {result}")
    return result


# ============================================================================
# Example 5: Using CLI Commands
# ============================================================================

def cli_examples():
    """
    CLI command examples (run in terminal):
    
    # Start a Temporal worker
    praisonai temporal worker --address localhost:7233 --concurrency 8

    # Check workflow status
    praisonai temporal status <workflow-id>

    # Send approval signal
    praisonai temporal approve <workflow-id> <task-id> --approved

    # Cancel a workflow
    praisonai temporal cancel <workflow-id> --reason "User requested"
    """
    pass


# ============================================================================
# Example 6: Docker Deployment
# ============================================================================

def docker_deployment():
    """
    Docker deployment example:

    1. Start Temporal server with UI:
       docker-compose -f docker/docker-compose.temporal.yml up -d

    2. Access Temporal UI at http://localhost:8080

    3. Workers are started automatically in the praisonai-worker container

    4. Scale workers:
       docker-compose -f docker/docker-compose.temporal.yml up -d --scale praisonai-worker=3
    """
    pass


# ============================================================================
# Example 7: Workflow Patterns
# ============================================================================

async def route_pattern():
    from temporalio.client import Client
    from praisonaiagents.temporal.workflows import WorkflowPatternWorkflow, WorkflowPatternInput

    client = await Client.connect("localhost:7233")

    input_data = WorkflowPatternInput(
        pattern_type="route",
        pattern_config={
            "condition": "Is this a technical or billing question?",
            "condition_agent": {"name": "classifier", "instructions": "Classify questions"},
            "routes": {
                "technical": [{"name": "tech_support", "instructions": "Help with technical issues"}],
                "billing": [{"name": "billing_agent", "instructions": "Help with billing"}],
            },
            "default": [{"name": "general_agent", "instructions": "General assistance"}],
            "task": "Help the customer"
        },
        agents_config=[],
        context={}
    )

    result = await client.execute_workflow(
        WorkflowPatternWorkflow.run,
        input_data,
        id="route-example",
        task_queue="praisonai-agents"
    )
    return result


async def loop_pattern():
    from temporalio.client import Client
    from praisonaiagents.temporal.workflows import WorkflowPatternWorkflow, WorkflowPatternInput

    client = await Client.connect("localhost:7233")

    input_data = WorkflowPatternInput(
        pattern_type="loop",
        pattern_config={
            "items": ["apple", "banana", "cherry"],
            "task_template": {
                "name": "process",
                "description": "Describe the fruit: {{item}}"
            },
            "agent": {"name": "fruit_expert", "instructions": "Describe fruits"}
        },
        agents_config=[],
        context={}
    )

    result = await client.execute_workflow(
        WorkflowPatternWorkflow.run,
        input_data,
        id="loop-example",
        task_queue="praisonai-agents"
    )
    return result


async def repeat_pattern():
    from temporalio.client import Client
    from praisonaiagents.temporal.workflows import WorkflowPatternWorkflow, WorkflowPatternInput

    client = await Client.connect("localhost:7233")

    input_data = WorkflowPatternInput(
        pattern_type="repeat",
        pattern_config={
            "max_iterations": 5,
            "generator": {"name": "writer", "instructions": "Write a haiku"},
            "evaluator": {"name": "reviewer", "instructions": "Say 'approved' if good, 'rejected' if not"},
            "task": {"name": "generate", "description": "Write a haiku about nature"}
        },
        agents_config=[],
        context={}
    )

    result = await client.execute_workflow(
        WorkflowPatternWorkflow.run,
        input_data,
        id="repeat-example",
        task_queue="praisonai-agents"
    )
    return result


# ============================================================================
# Example 8: Observability with Event Bridge
# ============================================================================

async def observability_example():
    from praisonaiagents import Agent, AgentTeam, Task
    from praisonaiagents.temporal import TemporalConfig
    from praisonaiagents.temporal.interceptors import (
        EventBusBridge,
        LoggingObserver,
        CompositeObserver,
        create_default_observer
    )
    import logging

    logging.basicConfig(level=logging.INFO)

    observer = CompositeObserver([
        LoggingObserver(level=logging.INFO),
        EventBusBridge()
    ])

    config = TemporalConfig(
        address="localhost:7233",
        interceptors=[observer]
    )

    agent = Agent(name="observer_test", instructions="Test agent")
    task = Task(name="test", description="Test task", agent=agent)

    team = AgentTeam(
        agents=[agent],
        tasks=[task],
        execution=config
    )

    result = team.start()
    return result


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        example = sys.argv[1]
        if example == "basic":
            asyncio.run(basic_temporal_execution())
        elif example == "config":
            asyncio.run(full_configuration())
        elif example == "parallel":
            asyncio.run(parallel_execution())
        elif example == "route":
            asyncio.run(route_pattern())
        elif example == "loop":
            asyncio.run(loop_pattern())
        elif example == "repeat":
            asyncio.run(repeat_pattern())
        elif example == "observe":
            asyncio.run(observability_example())
        else:
            print(f"Unknown example: {example}")
            print("Available: basic, config, parallel, route, loop, repeat, observe")
    else:
        print("Temporal Examples")
        print("=================")
        print("Run with: python temporal_examples.py <example>")
        print()
        print("Available examples:")
        print("  basic   - Basic Temporal execution")
        print("  config  - Full configuration options")
        print("  parallel - Parallel task execution")
        print("  route   - Route pattern (conditional branching)")
        print("  loop    - Loop pattern (iterate over items)")
        print("  repeat  - Repeat pattern (iterate until approved)")
        print("  observe - Observability with event bridge")
