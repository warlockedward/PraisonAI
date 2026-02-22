# PraisonAI Core SDK Internals (praisonaiagents)

**Parent:** `src/praisonai-agents/AGENTS.md` (Architecture, Philosophy, API)

## Module Map
| Module | Responsibility |
| :--- | :--- |
| `agent/`, `agents/` | Agent class, AgentTeam, multi-agent orchestration |
| `app/`, `bots/` | AgentApp, AgentOS, BotOS (Telegram, Discord, etc.) |
| `approval/`, `audit/` | Human-in-the-loop, Audit trail, logging |
| `bus/`, `hooks/` | EventBus (global events), Hook system (before/after tool) |
| `config/`, `context/` | Config dataclasses, Context management, artifacts |
| `db/`, `storage/` | DB adapters, Storage adapters |
| `embedding/`, `rag/` | Embedding protocols, RAG protocols, retriever |
| `eval/`, `obs/` | Evaluation framework, Observability adapters |
| `knowledge/` | Knowledge base, vector stores |
| `llm/`, `mcp/` | LLM client, model router, MCP client/server |
| `memory/`, `session/` | Memory protocols, Session management |
| `planning/`, `task/` | Planning module, Task class, protocols |
| `process/`, `workflows/` | Process modes, Workflow engine (Route, Loop, etc.) |
| `sandbox/` | Code execution sandbox (ONLY safe place) |
| `tools/`, `skills/` | Tool SDK, Agent skills |
| `ui/`, `output/` | Terminal UI, Output formatting |
| `utils/`, `paths.py` | Shared utilities, Centralized path resolution |
| `background/`, `scheduler/` | Background tasks, Schedule tools |
| `checkpoints/`, `snapshot/` | State checkpoints, State snapshots |
| `compaction/`, `thinking/` | Context compaction, Reasoning mode |
| `conditions/`, `policy/` | Workflow conditions, Policy engine |
| `escalation/`, `permissions/` | Task escalation, Permission system |
| `gateway/`, `server/` | API gateway, FastAPI server |
| `guardrails/`, `trace/` | Input/output guardrails, Trace protocols |
| `lsp/`, `profiling/` | LSP tools, Performance profiling |
| `streaming/`, `telemetry/` | Streaming events, PostHog telemetry |

## Key Files
| File | Role |
| :--- | :--- |
| `__init__.py` | Root exports + lazy loading via `_LAZY_IMPORTS` |
| `__init__new.py` | Experimental/new init approach |
| `_config.py`, `_lazy.py` | Internal config helpers, Lazy import machinery |
| `_logging.py`, `_warning_patch.py` | Logging setup, Warning suppression |
| `main.py`, `paths.py` | Entry point, Centralized path resolution |
| `flow_display.py`, `session.py` | Workflow visualization, Top-level session |

## Conventions
- **Lazy Loading:** All modules use lazy loading; check `__init__.py`'s `_LAZY_IMPORTS`.
- **Private Modules:** Prefixed with `_` (e.g., `_config.py`, `_lazy.py`).
- **Protocols:** Each major module has a `protocols.py` defining the interface.
- **Event Bus:** Use `bus/bus.py` for cross-module events.
- **Hooks:** `hooks/types.py` defines ALL hook event types.
- **Paths:** Use `paths.py` for ALL path resolution; NO hardcoded paths.
- **Telemetry:** PostHog based; disabled via `PRAISONAI_TELEMETRY=false`.
- **Sandbox:** `sandbox/` is the ONLY safe place for code execution.

## Gotchas
- `__init__new.py` exists alongside `__init__.py`; do NOT confuse them.
- `session.py` (top-level) vs `session/` (subpackage) are distinct.
- `process/process.py` contains DEPRECATED methods; verify before use.
- `_warning_patch.py` suppresses litellm/chromadb warnings; do not remove.
