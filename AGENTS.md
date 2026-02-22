# PraisonAI Monorepo Knowledge Base

**Generated:** 2026-02-21 | **Branch:** main | **Commit:** 440d35a9
**Stack:** Python (Primary), TypeScript, Rust

## Overview
Multi-language agentic AI framework monorepo. Centralized logic in Python core, with parallel implementations in TS and Rust.

## Repository Structure
```text
PraisonAI/
├── src/
│   ├── praisonai-agents/    # Core Python SDK (praisonaiagents)
│   ├── praisonai/           # Wrapper/CLI Python package (PraisonAI)
│   ├── praisonai-ts/        # TypeScript SDK (praisonai)
│   └── praisonai-rust/      # Rust SDK (praisonai)
├── examples/                # 70+ examples by language/topic
├── docker/                  # Deployment configurations
└── .github/workflows/       # 25 CI/CD workflows
```

## Package Hierarchy
- `praisonai` (Wrapper) -> wraps -> `praisonaiagents` (Core SDK)
- `praisonai-ts` (TypeScript) -> Parallel implementation
- `praisonai-rust` (Rust) -> Parallel implementation

## Core Philosophy
- **Agent-Centric:** Design revolves around Agent entities.
- **Protocol-Driven:** Core SDK uses protocols/hooks/adapters; minimal implementation.
- **Lazy Imports:** Optional dependencies NEVER imported at module level (<200ms import target).
- **Async-Safe:** No shared mutable global state; multi-agent safe.
- **DRY:** Reuse abstractions; avoid duplication across packages.

## Where To Look
| Task | Location |
| :--- | :--- |
| Agent class (Python) | `src/praisonai-agents/praisonaiagents/agent/agent.py` |
| Tool decorator (Python) | `src/praisonai-agents/praisonaiagents/tools/decorator.py` |
| CLI entry point | `src/praisonai/praisonai/cli/main.py` |
| CLI commands | `src/praisonai/praisonai/cli/commands/` |
| CLI features | `src/praisonai/praisonai/cli/features/` |
| Memory protocols | `src/praisonai-agents/praisonaiagents/memory/protocols.py` |
| Hook system | `src/praisonai-agents/praisonaiagents/hooks/` |
| Event bus | `src/praisonai-agents/praisonaiagents/bus/bus.py` |
| TS Agent class | `src/praisonai-ts/src/agent/simple.ts` |
| Rust Core crate | `src/praisonai-rust/praisonai/src/` |
| Python Examples | `examples/python/` |
| YAML Configs | `examples/yaml/` |

## Build & Test Commands
### Python (Core & Wrapper)
```bash
# Core SDK
cd src/praisonai-agents && pytest tests/unit/
uv pip install --system "praisonaiagents[knowledge]"

# Wrapper
cd src/praisonai && python -m pytest tests/unit/ -v
uv pip install --system ".[ui,gradio,api,agentops,google,openai,anthropic,chat,code]"
```

### TypeScript
```bash
cd src/praisonai-ts && npm test && npm run build
```

### Rust
```bash
cd src/praisonai-rust && cargo test && cargo build --release
```

## CI/CD
- **GitHub Actions:** 25 workflows (test-core.yml, unittest.yml, coverage.yml).
- **Manager:** `uv` preferred for Python in CI.
- **Versions:** Python 3.10, 3.11.
- **Markers:** `-m real` (live APIs), `--pattern fast` (quick tests).

## Anti-Patterns
- ❌ **Module-level optional imports:** No `chromadb`, `litellm` at top level.
- ❌ **Heavy Core:** No heavy implementations in `praisonaiagents`.
- ❌ **Shared State:** No mutable global state between agents.
- ❌ **Blocking Async:** No blocking I/O in async contexts.
- ❌ **Repetitive Actions:** Agents must not repeat the same action twice.
- ❌ **Deprecated Params:** Avoid `allow_code_execution`, `auto_save`, `allow_delegation`, `verification_hooks`. Use `Config` objects.
- ❌ **Legacy Code:** Avoid `scheduler.py` and `process/process.py`.

## Naming Conventions
- **Interfaces:** `XProtocol` (e.g., `MemoryProtocol`)
- **Implementations:** `XAdapter` (e.g., `MemoryAdapter`)
- **Configs:** `XConfig` (e.g., `ExecutionConfig`)
- **Registry:** `add_X()`, `register_X()`
- **Access:** `get_X()`, `list_X()`, `search_X()`
- **Persistence:** `save()` / `load()` (NOT `store()`)

## Docker
- `docker/Dockerfile`: API service
- `docker/Dockerfile.chat`: Chat UI
- `docker/Dockerfile.serve`: Serve mode
- `docker/docker-compose.yml`: Full stack deployment

## Notes & Gotchas
- Sub-AGENTS.md files exist for language-specific SDK internals.
- `praisonaiagents` is the source of truth for agent logic.
- Plugin template available at `examples/python/plugin_template/`.
- Always use `uv` for faster dependency management.
