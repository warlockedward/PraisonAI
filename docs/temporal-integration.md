# Temporal Execution Backend

PraisonAI supports Temporal as an optional execution backend for durable, scalable agent orchestration. This enables:

- **Durable Execution**: Workflows survive process crashes and restarts
- **Automatic Retries**: Built-in retry policies for failed activities
- **Human Approval**: Signal-based approval workflows
- **Observability**: Full visibility into agent execution via Temporal UI
- **Scalability**: Distribute agent execution across multiple workers

## Quick Start

### 1. Install Dependencies

```bash
pip install 'praisonaiagents[temporal]'
```

### 2. Start Temporal Server

```bash
# Using Docker Compose
docker-compose -f docker/docker-compose.temporal.yml up -d

# Or use Temporal CLI
temporal server start-dev
```

### 3. Use Temporal Backend

```python
from praisonaiagents import Agent, AgentTeam, Task

# Create agents
researcher = Agent(name="researcher", instructions="Research topics thoroughly")
writer = Agent(name="writer", instructions="Write clear summaries")

# Create tasks
t1 = Task(name="research", description="Research AI agents", agent=researcher)
t2 = Task(name="write", description="Write summary", agent=writer)

# Execute with Temporal backend
team = AgentTeam(
    agents=[researcher, writer],
    tasks=[t1, t2],
    execution="temporal"  # Enable Temporal
)

result = team.start()
```

## Configuration

### Minimal Configuration

```python
team = AgentTeam(
    agents=[agent1, agent2],
    tasks=[task1, task2],
    execution="temporal"
)
```

### Full Configuration

```python
from praisonaiagents.temporal import TemporalConfig
from datetime import timedelta

config = TemporalConfig(
    # Connection
    address="temporal.mycompany.com:7233",
    namespace="production",
    task_queue="praisonai-agents",

    # TLS (for production)
    tls=True,
    tls_cert_path="/path/to/cert.pem",
    tls_key_path="/path/to/key.pem",

    # Timeouts
    workflow_execution_timeout=timedelta(hours=24),
    default_activity_timeout=timedelta(minutes=10),

    # Retry Policy
    default_retry_policy={
        "maximum_attempts": 5,
        "initial_interval": 1,
        "backoff_coefficient": 2.0,
        "maximum_interval": 300,
    },

    # Worker Settings
    start_worker=True,
    worker_count=8
)

team = AgentTeam(
    agents=[agent1, agent2],
    tasks=[task1, task2],
    execution=config
)
```

### Configuration Reference

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `address` | str | `localhost:7233` | Temporal server address |
| `namespace` | str | `default` | Temporal namespace |
| `task_queue` | str | `praisonai-agents` | Task queue name |
| `tls` | bool | `False` | Enable TLS |
| `tls_cert_path` | str | `None` | Path to TLS certificate |
| `tls_key_path` | str | `None` | Path to TLS private key |
| `workflow_execution_timeout` | timedelta | 24 hours | Maximum workflow duration |
| `default_activity_timeout` | timedelta | 10 minutes | Default activity timeout |
| `default_retry_policy` | dict | See below | Default retry configuration |
| `start_worker` | bool | `True` | Start embedded worker |
| `worker_count` | int | `4` | Max concurrent activities |

Default retry policy:
```python
{
    "maximum_attempts": 5,
    "initial_interval": 1,      # seconds
    "backoff_coefficient": 2.0,
    "maximum_interval": 300,    # seconds
}
```

## Process Modes

### Sequential

Tasks execute one after another:

```python
team = AgentTeam(
    agents=[agent1, agent2],
    tasks=[task1, task2, task3],
    process="sequential",
    execution="temporal"
)
```

### Parallel

All tasks execute simultaneously:

```python
team = AgentTeam(
    agents=[agent1, agent2, agent3],
    tasks=[task1, task2, task3],
    process="parallel",
    execution="temporal"
)
```

### Hierarchical

Manager agent delegates to worker agents (planned):

```python
team = AgentTeam(
    agents=[manager, worker1, worker2],
    tasks=[task1, task2],
    process="hierarchical",
    execution="temporal"
)
```

## Human Approval

Enable human-in-the-loop workflows using Temporal signals:

### Workflow Side

```python
# In your workflow, request approval
await workflow.wait_condition(
    lambda: approval_received,
    timeout=timedelta(hours=24)
)
```

### Client Side

```python
from temporalio.client import Client

client = await Client.connect("localhost:7233")
handle = client.get_workflow_handle("workflow-id")

# Send approval signal
await handle.signal("approve_task", "task-1", True)  # Approved
await handle.signal("approve_task", "task-1", False) # Rejected
```

### CLI

```bash
# Approve a task
praisonai temporal approve <workflow-id> <task-id> --approved

# Reject a task
praisonai temporal approve <workflow-id> <task-id> --rejected
```

## CLI Commands

### Start Worker

```bash
praisonai temporal worker \
    --address localhost:7233 \
    --namespace default \
    --task-queue praisonai-agents \
    --concurrency 8
```

### Check Workflow Status

```bash
praisonai temporal status <workflow-id>
```

### Cancel Workflow

```bash
praisonai temporal cancel <workflow-id> --reason "User requested"
```

### Send Approval Signal

```bash
praisonai temporal approve <workflow-id> <task-id> --approved
praisonai temporal approve <workflow-id> <task-id> --rejected
```

## Docker Deployment

### Development

```bash
# Start Temporal server + UI + worker
docker-compose -f docker/docker-compose.temporal.yml up -d

# Access Temporal UI at http://localhost:8080
```

### Production

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  temporal:
    image: temporalio/server:latest
    environment:
      - DB=postgresql
      - DB_PORT=5432
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PWD=${POSTGRES_PASSWORD}
      - POSTGRES_SEEDS=postgres
    # ... production configuration

  praisonai-worker:
    build: .
    command: ["python", "-m", "praisonai", "temporal", "worker"]
    environment:
      - TEMPORAL_ADDRESS=temporal:7233
      - TEMPORAL_NAMESPACE=production
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    deploy:
      replicas: 3  # Scale workers
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      User Application                        │
│                                                             │
│  ┌─────────────────┐    ┌─────────────────────────────┐   │
│  │   AgentTeam     │    │      ExecutionBackend        │   │
│  │                 │───▶│  ┌─────────────────────────┐ │   │
│  │  agents: [...]  │    │  │ LocalExecutionBackend   │ │   │
│  │  tasks: [...]   │    │  └─────────────────────────┘ │   │
│  │  execution:     │    │  ┌─────────────────────────┐ │   │
│  │    "temporal"   │    │  │ TemporalExecutionBackend│ │   │
│  └─────────────────┘    │  └─────────────────────────┘ │   │
│                         └─────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────┐
│                     Temporal Server                          │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              AgentTeamWorkflow                       │   │
│  │                                                      │   │
│  │   Task 1 ──▶ Task 2 ──▶ Task 3 (sequential)         │   │
│  │   ┌─────┐      ┌─────┐      ┌─────┐                 │   │
│  │   │Task1│      │Task2│      │Task3│  (parallel)     │   │
│  │   └─────┘      └─────┘      └─────┘                 │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────┐
│                    Temporal Workers                          │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   Worker 1  │  │   Worker 2  │  │   Worker 3  │        │
│  │             │  │             │  │             │        │
│  │ [Activity]  │  │ [Activity]  │  │ [Activity]  │        │
│  │ execute_    │  │ execute_    │  │ execute_    │        │
│  │ agent_task  │  │ agent_task  │  │ agent_task  │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

## Workflow Patterns

### Route Pattern

Route to different agents based on condition:

```python
from praisonaiagents.temporal.workflows import WorkflowPatternInput, WorkflowPatternWorkflow

input_data = WorkflowPatternInput(
    pattern_type="route",
    pattern_config={
        "condition": "Classify this request",
        "condition_agent": {"name": "classifier"},
        "routes": {
            "technical": [{"name": "tech_support"}],
            "billing": [{"name": "billing_agent"}],
        },
        "default": [{"name": "general_agent"}]
    },
    agents_config=[...]
)
```

### Loop Pattern

Process items in a loop:

```python
input_data = WorkflowPatternInput(
    pattern_type="loop",
    pattern_config={
        "items": ["item1", "item2", "item3"],
        "task_template": {
            "name": "process",
            "description": "Process {{item}}"
        },
        "agent": {"name": "processor"}
    },
    agents_config=[...]
)
```

### Repeat Pattern

Iterate until condition met:

```python
input_data = WorkflowPatternInput(
    pattern_type="repeat",
    pattern_config={
        "max_iterations": 5,
        "generator": {"name": "writer"},
        "evaluator": {"name": "reviewer"},
        "task": {"name": "generate", "description": "Write content"}
    },
    agents_config=[...]
)
```

## Observability

### Event Bridge

Connect Temporal events to PraisonAI's EventBus:

```python
from praisonaiagents.temporal.interceptors import (
    EventBusBridge,
    LoggingObserver,
    CompositeObserver,
    create_default_observer
)

# Create observer with EventBus integration
observer = create_default_observer(event_bus=my_event_bus)

# Or create custom composite
observer = CompositeObserver([
    LoggingObserver(level=logging.DEBUG),
    EventBusBridge(event_bus)
])
```

### Temporal UI

Access the Temporal Web UI at `http://localhost:8080` to:
- View running workflows
- See workflow history
- Debug failed activities
- Send signals
- Cancel workflows

## Troubleshooting

### Connection Refused

```
Error: Could not connect to Temporal server at localhost:7233
```

**Solution**: Ensure Temporal server is running:
```bash
docker-compose -f docker/docker-compose.temporal.yml up -d
```

### Activity Timeout

```
Error: Activity timed out after 10 minutes
```

**Solution**: Increase timeout in config:
```python
config = TemporalConfig(
    default_activity_timeout=timedelta(minutes=30)
)
```

### Import Error

```
ImportError: temporalio is required for the 'temporal' backend
```

**Solution**: Install temporalio:
```bash
pip install 'praisonaiagents[temporal]'
```

### Worker Not Processing Tasks

**Solution**: Check worker is connected:
```bash
praisonai temporal status <workflow-id>
```

Ensure task queue matches:
```python
config = TemporalConfig(
    task_queue="praisonai-agents"  # Must match worker
)
```

## Migration Guide

### From Local to Temporal

1. **No code changes required** - just add `execution="temporal"`:

```python
# Before (local execution)
team = AgentTeam(agents=[a], tasks=[t])
result = team.start()

# After (Temporal execution)
team = AgentTeam(agents=[a], tasks=[t], execution="temporal")
result = team.start()
```

2. **Start Temporal server**:
```bash
docker-compose -f docker/docker-compose.temporal.yml up -d
```

3. **Verify via UI**: Open http://localhost:8080

## Best Practices

1. **Use meaningful workflow IDs** for debugging:
```python
team = AgentTeam(
    agents=[...],
    tasks=[...],
    execution=TemporalConfig(...)
)
# Workflow ID is auto-generated, or track via logging
```

2. **Set appropriate timeouts** based on task complexity:
```python
config = TemporalConfig(
    default_activity_timeout=timedelta(minutes=30),  # Complex LLM calls
    workflow_execution_timeout=timedelta(hours=48)   # Long workflows
)
```

3. **Scale workers horizontally** in production:
```bash
# Run multiple worker processes
praisonai temporal worker &
praisonai temporal worker &
praisonai temporal worker &
```

4. **Use namespaces** to separate environments:
```python
# Development
TemporalConfig(namespace="dev")

# Production
TemporalConfig(namespace="prod")
```

5. **Monitor via Temporal UI** for failures and retries

## API Reference

### ExecutionBackendProtocol

```python
class ExecutionBackendProtocol(Protocol):
    async def execute_team(
        self,
        agents: List[Any],
        tasks: Dict[str, Any],
        process_mode: str,
        config: Dict[str, Any],
    ) -> Dict[str, Any]: ...

    async def execute_task(
        self,
        task: Any,
        agent: Any,
        context: str,
    ) -> Any: ...

    async def execute_workflow(
        self,
        steps: List[Any],
        input_data: str,
        variables: Dict[str, Any],
    ) -> Dict[str, Any]: ...

    async def get_status(self, execution_id: str) -> Dict[str, Any]: ...
    async def send_signal(self, execution_id: str, signal: str, data: Any) -> None: ...
    async def cancel(self, execution_id: str) -> None: ...
```

### TemporalConfig

```python
@dataclass
class TemporalConfig:
    address: str = "localhost:7233"
    namespace: str = "default"
    task_queue: str = "praisonai-agents"
    tls: bool = False
    tls_cert_path: Optional[str] = None
    tls_key_path: Optional[str] = None
    workflow_execution_timeout: timedelta = timedelta(hours=24)
    default_activity_timeout: timedelta = timedelta(minutes=10)
    default_retry_policy: Dict[str, Any] = field(...)
    start_worker: bool = True
    worker_count: int = 4
    data_converter: Optional[Any] = None
    interceptors: Optional[List[Any]] = None
```

### Serialization Functions

```python
def serialize_agent(agent: Agent) -> Dict[str, Any]: ...
def deserialize_agent(config: Dict[str, Any], tool_registry: Optional[Dict] = None) -> Agent: ...
def serialize_task(task: Task) -> Dict[str, Any]: ...
def deserialize_task(config: Dict[str, Any], agents_map: Optional[Dict] = None) -> Task: ...
def serialize_task_output(output: TaskOutput) -> Dict[str, Any]: ...
def deserialize_task_output(data: Dict[str, Any]) -> TaskOutput: ...
```
