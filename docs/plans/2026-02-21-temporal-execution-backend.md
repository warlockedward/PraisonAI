# Temporal Execution Backend for PraisonAI — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Integrate Temporal as an optional, protocol-driven execution backend for PraisonAI's agent runtime, enabling crash-resilient, observable, and recoverable agent workflows — while preserving 100% backward compatibility and zero-dependency operation for existing users.

**Architecture:** A new `ExecutionBackendProtocol` abstraction sits between `AgentTeam`/`Workflow` and the actual task dispatch. The existing in-process executor becomes `LocalExecutionBackend` (default). A new `TemporalExecutionBackend` wraps agent tasks, LLM calls, and tool executions as Temporal Activities, orchestrated by Temporal Workflows. Activation is opt-in via `execution="temporal"` parameter or `PRAISONAI_EXECUTION_BACKEND=temporal` env var.

**Tech Stack:** Python 3.10+, temporalio SDK (optional dependency), existing PraisonAI protocols/hooks

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Concept Mapping](#2-concept-mapping)
3. [Architecture Overview](#3-architecture-overview)
4. [New Components](#4-new-components)
5. [Execution Flow](#5-execution-flow)
6. [Configuration Design](#6-configuration-design)
7. [Integration Points](#7-integration-points)
8. [State Management](#8-state-management)
9. [Observability Bridge](#9-observability-bridge)
10. [Error Handling & Retries](#10-error-handling--retries)
11. [Migration Path](#11-migration-path)
12. [Risks & Mitigations](#12-risks--mitigations)
13. [Implementation Phases](#13-implementation-phases)
14. [Task Breakdown](#14-task-breakdown)

---

## 1. Executive Summary

PraisonAI currently runs all agent orchestration in-process: `AgentTeam` creates a `Process` that dispatches tasks sequentially/hierarchically/in-parallel, all within a single Python process. If the process crashes, all state is lost. There is no built-in retry for infrastructure failures (only LLM validation retries), no durable state persistence across restarts, and observability relies on opt-in hooks/telemetry.

By introducing Temporal as an **optional execution backend**, PraisonAI gains:
- **Crash resilience**: Workflows survive process restarts via event-sourced replay
- **Durable retries**: LLM calls, tool executions auto-retry with configurable backoff
- **Built-in observability**: Every activity, signal, and state transition is recorded in Temporal's history
- **Human-in-the-loop durability**: Approval signals can wait hours/days without holding process state
- **Scalability**: Workers can be horizontally scaled across machines

The integration follows PraisonAI's protocol-driven philosophy: a new `ExecutionBackendProtocol` with two implementations (`LocalExecutionBackend` — current behavior, `TemporalExecutionBackend` — new). Zero changes to user-facing API for existing users.

---

## 2. Concept Mapping

| PraisonAI Concept | Temporal Equivalent | Mapping Strategy |
|---|---|---|
| `AgentTeam.start()` | `Client.execute_workflow(AgentTeamWorkflow)` | Top-level workflow wrapping the entire multi-agent run |
| `Process.sequential()` | Sequential `execute_activity()` chain | Activities called in sequence within workflow |
| `Process.hierarchical()` | Manager workflow + child workflows | Manager as workflow, delegated tasks as child workflows |
| `Process.parallel()` | `asyncio.gather(*[execute_activity()])` | Parallel activity execution within workflow |
| `Task` execution | `@activity.defn` | Each task becomes an activity invocation |
| `Agent.chat()` / LLM call | `@activity.defn` (non-deterministic) | LLM calls MUST be activities (not deterministic) |
| Tool execution | `@activity.defn` | Tools are I/O, must be activities |
| `Task.max_retries` | `RetryPolicy(maximum_attempts=N)` | Direct mapping |
| `Task.retry_delay` | `RetryPolicy(initial_interval=N)` | Direct mapping |
| `Task.on_error="retry"` | `RetryPolicy` with backoff | Automatic retry via Temporal |
| `Task.skip_on_failure` | Try/except in workflow, continue | Workflow catches ActivityError, skips |
| Human approval (`approval/`) | `@workflow.signal` + `wait_condition` | Signal pauses workflow until approval received |
| `Workflow` patterns (Route) | Conditional logic in `@workflow.run` | Workflow code branches on activity results |
| `Workflow` patterns (Parallel) | `asyncio.gather()` in workflow | Multiple activities in parallel |
| `Workflow` patterns (Loop) | Python loop in `@workflow.run` | Deterministic loop calling activities |
| `Workflow` patterns (Repeat) | While loop with signal/condition | Evaluator-optimizer as workflow loop |
| `hooks/` events | Temporal interceptors + activity hooks | Bridge hooks to Temporal interceptors |
| `bus/` EventBus | Temporal custom search attributes + interceptors | Event emission within activities |
| `checkpoints/` | Temporal event history (automatic) | Temporal replaces manual checkpoints |
| `trace/` protocols | Temporal's built-in tracing | Map to OpenTelemetry via Temporal |
| `session/` management | Workflow ID = session ID | Natural mapping |
| `Task.status` transitions | Workflow/Activity state in Temporal | Query workflow for task states |
| `WorkflowContext` | Temporal workflow state (instance vars) | Workflow class holds state |
| `StepResult` | Activity return value | Direct mapping |

---

## 3. Architecture Overview

```
                    USER API (unchanged)
                    ┌──────────────────────┐
                    │  AgentTeam / Workflow │
                    │  agent.start()       │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │ ExecutionBackendProto │  ← NEW protocol
                    │  .execute_team()     │
                    │  .execute_workflow() │
                    │  .execute_task()     │
                    └──────┬───────┬───────┘
                           │       │
              ┌────────────▼──┐ ┌──▼─────────────┐
              │    Local      │ │   Temporal      │  ← NEW
              │   Backend     │ │   Backend       │
              │  (default)    │ │  (opt-in)       │
              │               │ │                 │
              │ Current       │ │ ┌─────────────┐ │
              │ Process()     │ │ │ Temporal     │ │
              │ in-process    │ │ │ Client       │ │
              │ execution     │ │ └──────┬──────┘ │
              └───────────────┘ │        │        │
                                │ ┌──────▼──────┐ │
                                │ │  Workflows   │ │
                                │ │ AgentTeamWF  │ │
                                │ │ TaskWF       │ │
                                │ └──────┬──────┘ │
                                │        │        │
                                │ ┌──────▼──────┐ │
                                │ │ Activities   │ │
                                │ │ LLMActivity  │ │
                                │ │ ToolActivity │ │
                                │ │ AgentActivity│ │
                                │ └─────────────┘ │
                                └─────────────────┘

                                │  Temporal Server  │
                                │  (external dep)   │
```

### Layer Separation (Following PraisonAI Conventions)

```
Core SDK (praisonaiagents)          Wrapper (praisonai) or Core
━━━━━━━━━━━━━━━━━━━━━━━━━━━         ━━━━━━━━━━━━━━━━━━━━━━━━━
✅ ExecutionBackendProtocol         ✅ TemporalExecutionBackend
✅ LocalExecutionBackend            ✅ Temporal Workflows
✅ TemporalConfig dataclass         ✅ Temporal Activities
✅ Backend registry                 ✅ Worker management
```

**Decision:** Place ALL Temporal code in `praisonaiagents/temporal/` as a lazy-loaded optional module (same pattern as `memory/`, `knowledge/`, `mcp/`). The `temporalio` dependency is optional, imported only when `execution="temporal"` is set.

---

## 4. New Components

### 4.1 New Files

```
src/praisonai-agents/praisonaiagents/
├── execution/                          # NEW package
│   ├── __init__.py                     # Exports: ExecutionBackendProtocol, get_backend
│   ├── protocols.py                    # ExecutionBackendProtocol definition
│   ├── local_backend.py               # LocalExecutionBackend (wraps current Process)
│   └── registry.py                     # Backend registry + factory
│
├── temporal/                           # NEW package (lazy-loaded)
│   ├── __init__.py                     # Lazy exports, ImportError guard
│   ├── backend.py                      # TemporalExecutionBackend (implements protocol)
│   ├── config.py                       # TemporalConfig dataclass
│   ├── workflows/                      # Temporal workflow definitions
│   │   ├── __init__.py
│   │   ├── agent_team_workflow.py      # Top-level multi-agent workflow
│   │   ├── task_workflow.py            # Single-task workflow (child)
│   │   └── workflow_pattern_workflow.py # Workflow patterns (Route/Parallel/Loop/Repeat)
│   ├── activities/                     # Temporal activity definitions
│   │   ├── __init__.py
│   │   ├── llm_activity.py            # LLM call activity (wraps Agent.chat internals)
│   │   ├── tool_activity.py           # Tool execution activity
│   │   └── agent_activity.py          # Full agent task execution activity
│   ├── worker.py                       # Worker setup and lifecycle
│   ├── converter.py                    # PraisonAI ↔ Temporal data conversion
│   ├── interceptors.py                 # Bridge PraisonAI hooks to Temporal interceptors
│   └── utils.py                        # Shared utilities
│
├── config/
│   └── temporal_config.py              # TemporalConfig added to config system (NEW file)
```

### 4.2 Modified Files (Surgical Changes)

| File | Change | Scope |
|---|---|---|
| `agents/agents.py` | Add `execution` param resolution for "temporal" | ~20 lines in `__init__`, ~10 lines in `start()`/`astart()` |
| `workflows/workflows.py` | Add backend dispatch in `Workflow.start()` | ~15 lines |
| `config/feature_configs.py` | Add `TemporalConfig` dataclass | ~30 lines |
| `config/presets.py` | Add `EXECUTION_BACKEND_PRESETS` | ~10 lines |
| `__init__.py` | Add lazy import for `TemporalConfig` | ~3 lines in `_LAZY_IMPORTS` |
| `pyproject.toml` | Add `[project.optional-dependencies] temporal` | ~3 lines |

### 4.3 Protocol Definition

```python
# execution/protocols.py
from typing import Protocol, Any, Dict, List, Optional
from ..task.task import Task
from ..agent.agent import Agent

class ExecutionBackendProtocol(Protocol):
    """Protocol for execution backends (local, temporal, etc.)"""

    async def execute_team(
        self,
        agents: List[Agent],
        tasks: Dict[str, Task],
        process: str,  # "sequential" | "parallel" | "hierarchical"
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a multi-agent team run."""
        ...

    async def execute_task(
        self,
        task: Task,
        agent: Agent,
        context: str,
    ) -> Any:
        """Execute a single task with an agent."""
        ...

    async def execute_workflow(
        self,
        steps: List[Any],
        input_data: str,
        variables: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a workflow (step-based)."""
        ...

    async def get_status(self, execution_id: str) -> Dict[str, Any]:
        """Query execution status."""
        ...

    async def send_signal(self, execution_id: str, signal: str, data: Any) -> None:
        """Send signal to running execution (e.g., human approval)."""
        ...

    async def cancel(self, execution_id: str) -> None:
        """Cancel a running execution."""
        ...
```

---

## 5. Execution Flow

### 5.1 Without Temporal (Current — LocalExecutionBackend)

```
User: team.start()
  → AgentTeam.start()
    → backend = get_backend("local")  # NEW: backend resolution
    → backend.execute_team(agents, tasks, "sequential")
      → LocalExecutionBackend.execute_team()
        → Process(tasks, agents).sequential()  # EXISTING code, unchanged
          → for task in tasks: agent.execute_task(task)
            → Agent.chat() → LLM call → tool calls → result
        → return results
```

**Impact:** Virtually zero — `LocalExecutionBackend` wraps existing `Process` class.

### 5.2 With Temporal (TemporalExecutionBackend)

```
User: team.start(execution="temporal")
  → AgentTeam.start()
    → backend = get_backend("temporal", config=temporal_config)
    → backend.execute_team(agents, tasks, "sequential")
      → TemporalExecutionBackend.execute_team()
        → client.execute_workflow(
            AgentTeamWorkflow.run,
            args=TeamInput(agents_config, tasks_config, "sequential"),
            id=f"team-{uuid}",
            task_queue="praisonai-agents",
          )

[Inside Temporal Worker — can be same or different process]

AgentTeamWorkflow.run(input: TeamInput):
    results = {}
    for task_config in input.tasks:
        # Each task is a Temporal Activity (durable, retried)
        result = await workflow.execute_activity(
            execute_agent_task,
            args=[task_config, agent_config, context],
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RetryPolicy(
                maximum_attempts=task_config.max_retries,
                initial_interval=timedelta(seconds=task_config.retry_delay or 1),
                backoff_coefficient=2.0,
            ),
        )
        results[task_config.id] = result

        # Handle conditional routing
        if task_config.condition:
            next_task = evaluate_condition(result, task_config.condition)
            # ... route to next task

        # Handle human approval if needed
        if task_config.requires_approval:
            await workflow.wait_condition(
                lambda: self._approvals.get(task_config.id),
                timeout=timedelta(hours=24),
            )

    return results

@activity.defn
async def execute_agent_task(task_config, agent_config, context) -> dict:
    """Activity: Execute a single agent task (non-deterministic, retried)."""
    # Reconstruct Agent and Task from serialized config
    agent = Agent(**agent_config)
    task = Task(**task_config)

    # This is where the actual LLM call + tool execution happens
    # All I/O is safe inside an activity
    result = agent.execute_task(task, context)
    return serialize_task_output(result)
```

### 5.3 Hierarchical Process with Temporal

```
AgentTeamWorkflow.run(input: TeamInput):  # process="hierarchical"
    # Manager decides task assignment (Activity)
    assignment = await workflow.execute_activity(
        manager_decide_assignment,
        args=[input.tasks, input.agents],
        ...
    )

    # Execute assigned tasks as child workflows (parallel)
    handles = []
    for agent_id, task_ids in assignment.items():
        handle = await workflow.start_child_workflow(
            AgentTaskWorkflow.run,
            args=[agent_config, task_configs],
            id=f"agent-{agent_id}-{uuid}",
        )
        handles.append(handle)

    results = await asyncio.gather(*handles)
    return merge_results(results)
```

### 5.4 Workflow Patterns with Temporal

```
WorkflowPatternWorkflow.run(input: WorkflowInput):
    for step in input.steps:
        if isinstance(step, RouteConfig):
            # Route: execute classifier, branch on result
            decision = await workflow.execute_activity(execute_step, ...)
            branch = step.routes.get(decision, step.default)
            for sub_step in branch:
                await workflow.execute_activity(execute_step, sub_step, ...)

        elif isinstance(step, ParallelConfig):
            # Parallel: fan-out activities
            await asyncio.gather(*[
                workflow.execute_activity(execute_step, s, ...)
                for s in step.steps
            ])

        elif isinstance(step, LoopConfig):
            # Loop: iterate over items
            for item in step.items:
                await workflow.execute_activity(execute_step, step.step, item, ...)

        elif isinstance(step, RepeatConfig):
            # Repeat: evaluator-optimizer loop
            for i in range(step.max_iterations):
                result = await workflow.execute_activity(execute_step, step.step, ...)
                if step.until(result):
                    break

        else:
            # Simple step: single activity
            await workflow.execute_activity(execute_step, step, ...)
```

---

## 6. Configuration Design

### 6.1 Minimal Configuration (3 lines)

```python
from praisonaiagents import Agent, AgentTeam

team = AgentTeam(
    agents=[agent1, agent2],
    tasks=[task1, task2],
    execution="temporal",  # ← Only change needed
)
result = team.start()
```

**Requires:** `TEMPORAL_ADDRESS=localhost:7233` env var (or defaults to `localhost:7233`).

### 6.2 Environment Variable Activation

```bash
export PRAISONAI_EXECUTION_BACKEND=temporal
export TEMPORAL_ADDRESS=localhost:7233
# Optional:
export TEMPORAL_NAMESPACE=default
export TEMPORAL_TASK_QUEUE=praisonai-agents
```

```python
# No code changes needed — backend auto-detected from env
team = AgentTeam(agents=[agent1, agent2], tasks=[task1, task2])
team.start()  # Uses Temporal automatically
```

### 6.3 Full Configuration

```python
from praisonaiagents import Agent, AgentTeam
from praisonaiagents.temporal import TemporalConfig

team = AgentTeam(
    agents=[agent1, agent2],
    tasks=[task1, task2],
    execution=TemporalConfig(
        address="temporal.mycompany.com:7233",
        namespace="production",
        task_queue="ai-agents",
        tls=True,
        tls_cert_path="/path/to/cert.pem",
        tls_key_path="/path/to/key.pem",
        workflow_execution_timeout=timedelta(hours=24),
        default_activity_timeout=timedelta(minutes=10),
        default_retry_policy={
            "maximum_attempts": 5,
            "initial_interval": timedelta(seconds=1),
            "backoff_coefficient": 2.0,
            "maximum_interval": timedelta(minutes=5),
        },
        start_worker=True,  # Auto-start worker in same process
        worker_count=4,     # Concurrent activity slots
    ),
)
```

### 6.4 TemporalConfig Dataclass

```python
# config/temporal_config.py
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Optional, Dict, Any

@dataclass
class TemporalConfig:
    """Configuration for Temporal execution backend."""
    # Connection
    address: str = "localhost:7233"
    namespace: str = "default"
    task_queue: str = "praisonai-agents"

    # TLS
    tls: bool = False
    tls_cert_path: Optional[str] = None
    tls_key_path: Optional[str] = None

    # Timeouts
    workflow_execution_timeout: timedelta = field(default_factory=lambda: timedelta(hours=24))
    default_activity_timeout: timedelta = field(default_factory=lambda: timedelta(minutes=10))

    # Retry defaults (applied to all activities unless task overrides)
    default_retry_policy: Dict[str, Any] = field(default_factory=lambda: {
        "maximum_attempts": 5,
        "initial_interval": 1,  # seconds
        "backoff_coefficient": 2.0,
        "maximum_interval": 300,  # seconds
    })

    # Worker
    start_worker: bool = True  # Start embedded worker
    worker_count: int = 4  # Max concurrent activities

    # Advanced
    data_converter: Optional[Any] = None  # Custom Temporal DataConverter
    interceptors: Optional[list] = None  # Temporal interceptors
```

### 6.5 Per-Task Overrides

Existing `Task` parameters map directly:

```python
task = Task(
    description="Complex analysis",
    agent=researcher,
    max_retries=5,           # → RetryPolicy.maximum_attempts
    retry_delay=2.0,         # → RetryPolicy.initial_interval
    on_error="retry",        # → Enable RetryPolicy
    skip_on_failure=True,    # → Catch ActivityError, continue
)
```

No new Task parameters needed — existing robustness params are sufficient.

---

## 7. Integration Points

### 7.1 AgentTeam (agents/agents.py)

**Change:** Add backend resolution in `__init__` and dispatch in `start()`/`astart()`.

```python
# In __init__ — add after execution config resolution (~line 310)
self._execution_backend_config = execution  # Store raw for backend resolution

# In start() — replace direct Process() call
async def astart(self):
    from ..execution import get_backend
    backend = get_backend(self._execution_backend_config)
    return await backend.execute_team(
        agents=self.agents,
        tasks=self.tasks,
        process=self.process,
        config=self._build_backend_config(),
    )
```

**Scope:** ~30 lines changed in a 2415-line file.

### 7.2 Workflow (workflows/workflows.py)

**Change:** Add optional backend dispatch in `start()`.

```python
# In Workflow.start() — add backend check before existing execution
async def astart(self, input_data, **kwargs):
    backend = kwargs.get('execution') or self._execution_backend
    if backend and backend != "local":
        from ..execution import get_backend
        b = get_backend(backend)
        return await b.execute_workflow(self.steps, input_data, self.variables)
    # ... existing execution logic (unchanged)
```

**Scope:** ~15 lines.

### 7.3 Process (process/process.py)

**Change:** NONE. Process is wrapped by `LocalExecutionBackend`, not modified.

### 7.4 pyproject.toml

```toml
[project.optional-dependencies]
temporal = ["temporalio>=1.9.0"]
```

---

## 8. State Management

### 8.1 State Comparison

| Aspect | Local Backend | Temporal Backend |
|---|---|---|
| Task status | `task.status` in memory | Temporal workflow state (event-sourced) |
| Task results | `task.result` in memory | Activity return values (persisted) |
| Crash recovery | Lost | Automatic replay from event history |
| Checkpoints | Manual (`checkpoints/`) | Automatic (every activity completion) |
| Session state | `session/` module | Workflow ID = session, durable |
| Long waits | Process must stay alive | Workflow paused, worker can restart |

### 8.2 Serialization Strategy

Temporal requires all workflow/activity inputs/outputs to be serializable. Key decisions:

1. **Agent config** → Serialize as dict (constructor kwargs), reconstruct in activity
2. **Task config** → Serialize as dict (all params), reconstruct in activity
3. **Task results** → Serialize `TaskOutput` as dict (raw, json_dict, pydantic_output)
4. **Tool functions** → Reference by name (tool registry lookup in activity)
5. **LLM responses** → Already JSON-serializable

```python
# converter.py
def serialize_agent(agent: Agent) -> dict:
    """Serialize Agent to reconstructable config dict."""
    return {
        "name": agent.name,
        "role": agent.role,
        "goal": agent.goal,
        "instructions": agent.instructions,
        "llm": agent.llm,
        "tools": [tool.__name__ if callable(tool) else tool for tool in agent.tools],
        # ... other serializable params
    }

def deserialize_agent(config: dict) -> Agent:
    """Reconstruct Agent from config dict."""
    # Resolve tool references back to callables
    tools = resolve_tools(config.pop("tools", []))
    return Agent(tools=tools, **config)
```

### 8.3 Large Payload Handling

Temporal has event history size limits (~50K events, payload limits). For long conversations:

- **Claim-check pattern**: Store large payloads (conversation history, embeddings) in external storage (S3/Redis), pass reference in workflow
- **Continue-as-new**: For very long agent loops, use `workflow.continue_as_new()` to reset history while preserving state
- **Conversation compaction**: Leverage existing `compaction/` module before serializing

---

## 9. Observability Bridge

### 9.1 PraisonAI Hooks → Temporal

```python
# interceptors.py
from temporalio.worker import ActivityInboundInterceptor, WorkflowInboundInterceptor

class PraisonAIActivityInterceptor(ActivityInboundInterceptor):
    """Bridge PraisonAI hooks to Temporal activity lifecycle."""

    async def execute_activity(self, input):
        # Fire PraisonAI hook: before_task
        hook_runner.fire(HookEvent.BEFORE_TASK, {
            "task_name": input.fn.__name__,
            "args": input.args,
        })

        try:
            result = await super().execute_activity(input)
            # Fire: after_task
            hook_runner.fire(HookEvent.AFTER_TASK, {
                "task_name": input.fn.__name__,
                "result": result,
            })
            return result
        except Exception as e:
            # Fire: on_error
            hook_runner.fire(HookEvent.ON_ERROR, {
                "task_name": input.fn.__name__,
                "error": str(e),
            })
            raise
```

### 9.2 Temporal → PraisonAI EventBus

```python
# In activities — emit events to PraisonAI bus
@activity.defn
async def execute_agent_task(task_config, agent_config, context):
    from ..bus import get_default_bus
    bus = get_default_bus()

    bus.emit("temporal.activity.started", {
        "task_id": task_config["id"],
        "attempt": activity.info().attempt,
    })

    result = ...  # execute task

    bus.emit("temporal.activity.completed", {
        "task_id": task_config["id"],
        "duration_ms": ...,
    })
    return result
```

### 9.3 Temporal UI Integration

Temporal provides a web UI (typically at `localhost:8233`) showing:
- All running/completed workflows
- Activity execution details with timing
- Event history replay
- Signal/query inspection

This supplements (not replaces) PraisonAI's existing `trace/` and `telemetry/`.

---

## 10. Error Handling & Retries

### 10.1 Retry Policy Mapping

```python
# In TemporalExecutionBackend — build RetryPolicy from Task params
def _build_retry_policy(self, task: Task) -> RetryPolicy:
    if task.on_error == "stop":
        return RetryPolicy(maximum_attempts=1)  # No retry
    elif task.on_error == "retry":
        return RetryPolicy(
            maximum_attempts=task.max_retries or 3,
            initial_interval=timedelta(seconds=task.retry_delay or 1),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(minutes=5),
            non_retryable_error_types=["ValueError", "ValidationError"],
        )
    else:  # "continue"
        return RetryPolicy(maximum_attempts=1)  # Fail fast, workflow continues
```

### 10.2 Non-Retryable vs Retryable Errors

| Error Type | Retryable? | Reason |
|---|---|---|
| LLM API timeout/5xx | Yes | Transient infrastructure failure |
| LLM rate limit (429) | Yes | Back off and retry |
| Tool network error | Yes | Transient |
| LLM validation failure | Yes (limited) | Model might produce valid output on retry |
| Invalid API key | No | Configuration error, retrying won't help |
| Task ValueError | No | Logic error in task definition |
| Guardrail rejection | Configurable | Depends on guardrail type |

### 10.3 Failure Handling in Workflow

```python
# In AgentTeamWorkflow
for task_config in input.tasks:
    try:
        result = await workflow.execute_activity(
            execute_agent_task, ...,
            retry_policy=self._build_retry_policy(task_config),
        )
        results[task_config["id"]] = result
    except ActivityError as e:
        if task_config.get("skip_on_failure"):
            results[task_config["id"]] = {"status": "skipped", "error": str(e)}
            continue
        elif task_config.get("on_error") == "continue":
            results[task_config["id"]] = {"status": "failed", "error": str(e)}
            continue
        else:
            raise  # Propagate to workflow level
```

---

## 11. Migration Path

### Step 1: Install Dependencies (1 minute)
```bash
pip install "praisonaiagents[temporal]"
# Start Temporal dev server
temporal server start-dev
```

### Step 2: Test with Single Agent (5 minutes)
```python
from praisonaiagents import Agent

agent = Agent(
    name="test",
    instructions="Be helpful",
    execution="temporal",  # Add this one param
)
result = agent.start("Hello!")
```

### Step 3: Convert Multi-Agent Team (5 minutes)
```python
team = AgentTeam(
    agents=[researcher, writer],
    tasks=[task1, task2],
    execution="temporal",  # Add this one param
)
result = team.start()
```

### Step 4: Full Production Config (30 minutes)
```python
from praisonaiagents.temporal import TemporalConfig

config = TemporalConfig(
    address="temporal.mycompany.com:7233",
    namespace="production",
    tls=True,
    tls_cert_path="/certs/client.pem",
    tls_key_path="/certs/client-key.pem",
    task_queue="ai-agents-prod",
    start_worker=False,  # Run workers separately
)

# Deploy workers separately
# python -m praisonaiagents.temporal.worker --config prod.yaml
```

### Step 5: Leverage Temporal Features (ongoing)
- Add human approval signals to critical tasks
- Monitor via Temporal UI
- Scale workers independently
- Use Temporal schedules for recurring agent runs

---

## 12. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Serialization failures | Agent/Task not serializable | Comprehensive converter.py with tests for all param types |
| Temporal server dependency | Users must run Temporal | Embedded dev server option, clear docs, Docker compose |
| Non-deterministic workflows | Workflow replay failures | ALL I/O in activities, workflow code is pure logic |
| Large conversation histories | Temporal payload limits | Claim-check pattern + continue-as-new + compaction |
| Tool function serialization | Can't serialize lambdas | Tool registry lookup by name, not direct serialization |
| Performance overhead | Network hop for each activity | Batch activities, local activity option for fast ops |
| Complexity increase | Learning curve for Temporal | Zero-config defaults, "just add `execution='temporal'`" |
| MCP tools in activities | MCP connections not serializable | Establish MCP connections inside activities, not workflows |
| Memory/Knowledge with Temporal | State sharing between activities | Pass memory config, reconstruct in each activity |

---

## 13. Implementation Phases

### Phase 1: Foundation (Week 1-2) — HIGH PRIORITY
- [ ] Create `execution/` package with protocol + local backend
- [ ] Refactor `AgentTeam.start()` to use backend dispatch
- [ ] Ensure 100% backward compatibility (all existing tests pass)
- [ ] Add `temporal` optional dependency to pyproject.toml

### Phase 2: Core Temporal Backend (Week 2-4) — HIGH PRIORITY
- [ ] Create `temporal/` package structure
- [ ] Implement `TemporalConfig` dataclass
- [ ] Implement agent/task serialization (`converter.py`)
- [ ] Implement `execute_agent_task` activity
- [ ] Implement `AgentTeamWorkflow` (sequential process)
- [ ] Implement `TemporalExecutionBackend`
- [ ] Implement embedded worker management
- [ ] Write integration tests with Temporal test server

### Phase 3: Process Modes (Week 4-5) — MEDIUM PRIORITY
- [ ] Implement hierarchical process as child workflows
- [ ] Implement parallel process with concurrent activities
- [ ] Add human approval signal support
- [ ] Map Workflow patterns (Route, Parallel, Loop, Repeat)

### Phase 4: Observability Bridge (Week 5-6) — MEDIUM PRIORITY
- [ ] Implement PraisonAI interceptors for Temporal
- [ ] Bridge hooks/EventBus events
- [ ] Add Temporal-aware trace protocol adapter
- [ ] Emit structured logs with workflow/activity IDs

### Phase 5: Production Hardening (Week 6-8) — HIGH PRIORITY
- [ ] Implement claim-check pattern for large payloads
- [ ] Implement continue-as-new for long-running workflows
- [ ] Add TLS support
- [ ] Add comprehensive error handling and non-retryable classification
- [ ] Performance benchmarking (local vs Temporal overhead)
- [ ] Documentation + examples

### Phase 6: CLI & DevX (Week 8-9) — LOW PRIORITY
- [ ] Add `praisonai temporal worker` CLI command
- [ ] Add `praisonai temporal status` CLI command
- [ ] Docker compose with Temporal server
- [ ] Migration guide documentation

---

## 14. Task Breakdown

### Task 1: Create ExecutionBackendProtocol and LocalExecutionBackend

**Files:**
- Create: `src/praisonai-agents/praisonaiagents/execution/__init__.py`
- Create: `src/praisonai-agents/praisonaiagents/execution/protocols.py`
- Create: `src/praisonai-agents/praisonaiagents/execution/local_backend.py`
- Create: `src/praisonai-agents/praisonaiagents/execution/registry.py`
- Test: `src/praisonai-agents/tests/unit/test_execution_backend.py`

**Step 1: Write the failing test**

```python
import pytest
from praisonaiagents.execution import get_backend, ExecutionBackendProtocol
from praisonaiagents.execution.local_backend import LocalExecutionBackend

def test_get_backend_returns_local_by_default():
    backend = get_backend(None)
    assert isinstance(backend, LocalExecutionBackend)

def test_get_backend_returns_local_explicitly():
    backend = get_backend("local")
    assert isinstance(backend, LocalExecutionBackend)

def test_local_backend_implements_protocol():
    backend = LocalExecutionBackend()
    assert isinstance(backend, ExecutionBackendProtocol)

def test_get_backend_temporal_without_install():
    with pytest.raises(ImportError, match="temporalio"):
        get_backend("temporal")
```

**Step 2: Run test to verify it fails**

Run: `cd src/praisonai-agents && pytest tests/unit/test_execution_backend.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Implement protocol and local backend**

See Section 4.3 for `ExecutionBackendProtocol`.
`LocalExecutionBackend` wraps existing `Process` class call.
`registry.py` provides `get_backend()` factory.

**Step 4: Run test to verify it passes**

Run: `cd src/praisonai-agents && pytest tests/unit/test_execution_backend.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/praisonai-agents/praisonaiagents/execution/ tests/unit/test_execution_backend.py
git commit -m "feat(execution): add ExecutionBackendProtocol and LocalExecutionBackend"
```

---

### Task 2: Wire AgentTeam to use ExecutionBackend

**Files:**
- Modify: `src/praisonai-agents/praisonaiagents/agents/agents.py` (lines ~200-310, ~start methods)
- Test: `src/praisonai-agents/tests/unit/test_agents_backend_dispatch.py`

**Step 1: Write the failing test**

```python
from praisonaiagents import Agent, AgentTeam

def test_agent_team_accepts_execution_param():
    agent = Agent(name="test", instructions="Be helpful")
    team = AgentTeam(agents=[agent], execution="local")
    assert team._execution_backend_config == "local"

def test_agent_team_default_execution_is_none():
    agent = Agent(name="test", instructions="Be helpful")
    team = AgentTeam(agents=[agent])
    assert team._execution_backend_config is None  # defaults to local
```

**Step 2-5:** Standard TDD cycle + commit.

---

### Task 3: Create TemporalConfig dataclass

**Files:**
- Create: `src/praisonai-agents/praisonaiagents/temporal/__init__.py`
- Create: `src/praisonai-agents/praisonaiagents/temporal/config.py`
- Test: `src/praisonai-agents/tests/unit/test_temporal_config.py`

---

### Task 4: Implement Agent/Task serialization (converter.py)

**Files:**
- Create: `src/praisonai-agents/praisonaiagents/temporal/converter.py`
- Test: `src/praisonai-agents/tests/unit/test_temporal_converter.py`

---

### Task 5: Implement execute_agent_task Activity

**Files:**
- Create: `src/praisonai-agents/praisonaiagents/temporal/activities/__init__.py`
- Create: `src/praisonai-agents/praisonaiagents/temporal/activities/agent_activity.py`
- Test: `src/praisonai-agents/tests/unit/test_temporal_activities.py`

---

### Task 6: Implement AgentTeamWorkflow (sequential)

**Files:**
- Create: `src/praisonai-agents/praisonaiagents/temporal/workflows/__init__.py`
- Create: `src/praisonai-agents/praisonaiagents/temporal/workflows/agent_team_workflow.py`
- Test: `src/praisonai-agents/tests/integration/test_temporal_workflow.py`

---

### Task 7: Implement TemporalExecutionBackend

**Files:**
- Create: `src/praisonai-agents/praisonaiagents/temporal/backend.py`
- Create: `src/praisonai-agents/praisonaiagents/temporal/worker.py`
- Modify: `src/praisonai-agents/praisonaiagents/execution/registry.py` (add temporal registration)
- Test: `src/praisonai-agents/tests/integration/test_temporal_backend.py`

---

### Task 8: Implement Hierarchical + Parallel processes

**Files:**
- Modify: `src/praisonai-agents/praisonaiagents/temporal/workflows/agent_team_workflow.py`
- Create: `src/praisonai-agents/praisonaiagents/temporal/workflows/task_workflow.py`
- Test: `src/praisonai-agents/tests/integration/test_temporal_processes.py`

---

### Task 9: Implement Workflow pattern mapping

**Files:**
- Create: `src/praisonai-agents/praisonaiagents/temporal/workflows/workflow_pattern_workflow.py`
- Test: `src/praisonai-agents/tests/integration/test_temporal_workflow_patterns.py`

---

### Task 10: Implement observability bridge (interceptors)

**Files:**
- Create: `src/praisonai-agents/praisonaiagents/temporal/interceptors.py`
- Test: `src/praisonai-agents/tests/unit/test_temporal_interceptors.py`

---

### Task 11: Add human approval signal support

**Files:**
- Modify: `src/praisonai-agents/praisonaiagents/temporal/workflows/agent_team_workflow.py`
- Test: `src/praisonai-agents/tests/integration/test_temporal_signals.py`

---

### Task 12: Add CLI commands for Temporal worker

**Files:**
- Create: `src/praisonai/praisonai/cli/commands/temporal.py`
- Modify: `src/praisonai/praisonai/cli/app.py` (register temporal commands)
- Test: `src/praisonai/tests/unit/cli/test_temporal_cli.py`

---

### Task 13: Add pyproject.toml optional dependency + docs

**Files:**
- Modify: `src/praisonai-agents/pyproject.toml`
- Create: `examples/python/temporal/basic_temporal_agent.py`
- Create: `examples/python/temporal/temporal_multi_agent.py`

---

### Task 14: Docker compose with Temporal server

**Files:**
- Create: `docker/docker-compose.temporal.yml`

---

### Task 15: End-to-end integration tests

**Files:**
- Create: `src/praisonai-agents/tests/integration/test_temporal_e2e.py`

**Verification:** Run with Temporal test server, verify:
- Sequential multi-agent runs complete
- Worker restart doesn't lose state
- Retry on LLM failure works
- Human approval signal works
- All existing tests still pass

---

> **End of Plan**
