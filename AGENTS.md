# PraisonAI Monorepo Knowledge Base

**Updated:** 2026-02-22 | **Stack:** Python (Primary), TypeScript, Rust

## Overview
Multi-language agentic AI framework monorepo. Centralized logic in Python core, with parallel implementations in TS and Rust.

## Repository Structure
```
PraisonAI/
├── src/
│   ├── praisonai-agents/    # Core Python SDK (praisonaiagents)
│   ├── praisonai/           # Wrapper/CLI Python package
│   ├── praisonai-ts/        # TypeScript SDK
│   └── praisonai-rust/      # Rust SDK
├── examples/                # 70+ examples by language/topic
└── .github/workflows/       # 25 CI/CD workflows
```

## Build & Test Commands

### Python (Core SDK)
```bash
cd src/praisonai-agents

# Run all unit tests
pytest tests/unit/ -v

# Run specific test file
pytest tests/unit/temporal/test_temporal_converter.py -v

# Run specific test
pytest tests/unit/temporal/test_temporal_converter.py::test_serialize_agent -v

# Run with markers
pytest tests/unit/ -m "not slow" -v
pytest tests/unit/ -m "integration" -v
pytest tests/ -m "live" -v  # Real API calls

# Run with timeout override
pytest tests/unit/ --override-ini="addopts=" -v

# Install with extras
uv pip install --system "praisonaiagents[knowledge]"
uv pip install --system "praisonaiagents[temporal]"
```

### TypeScript
```bash
cd src/praisonai-ts
npm test                    # All tests
npm test -- tests/unit/agent.test.ts  # Single file
npm run build              # Compile
npm run lint               # Lint check
```

### Rust
```bash
cd src/praisonai-rust
cargo test                 # All tests
cargo test --test <name>   # Single test
cargo build --release      # Release build
```

## Core Philosophy

| Principle | Description |
|-----------|-------------|
| **Agent-Centric** | Design revolves around Agent entities |
| **Protocol-Driven** | Core SDK uses protocols/hooks/adapters; minimal implementation |
| **Lazy Imports** | Optional dependencies NEVER imported at module level (<200ms import target) |
| **Async-Safe** | No shared mutable global state; multi-agent safe |
| **DRY** | Reuse abstractions; avoid duplication |
| **LESS IS MORE** | Minimal code changes; modify existing code only when required |

## Code Style Guidelines

### Imports
```python
# ✅ CORRECT: Lazy import for optional dependencies
def use_chromadb():
    try:
        import chromadb
    except ImportError:
        raise ImportError("Install with: pip install praisonaiagents[memory]")

# ❌ WRONG: Module-level heavy import
import chromadb  # Adds 500ms+ to import time
```

### Naming Conventions
| Pattern | Example |
|---------|---------|
| Interfaces | `XProtocol` (e.g., `MemoryProtocol`) |
| Implementations | `XAdapter` (e.g., `MemoryAdapter`) |
| Configs | `XConfig` (e.g., `ExecutionConfig`) |
| Registration | `add_X()`, `register_X()` |
| Retrieval | `get_X()`, `list_X()`, `search_X()` |
| Persistence | `save()` / `load()` (NOT `store()`) |

### Error Handling
```python
# Use specific exceptions with remediation hints
raise ImportError(
    "The 'temporal' backend requires 'temporalio'. "
    "Install with: pip install 'praisonaiagents[temporal]'"
)
```

### Type Annotations
```python
# All public APIs must have type hints
def execute_task(
    self,
    task: Task,
    agent: Agent,
    context: str,
) -> TaskOutput:
    ...
```

## Where To Look
| Task | Location |
|------|----------|
| Agent class (Python) | `src/praisonai-agents/praisonaiagents/agent/agent.py` |
| Tool decorator | `src/praisonai-agents/praisonaiagents/tools/decorator.py` |
| CLI entry point | `src/praisonai/praisonai/cli/main.py` |
| Memory protocols | `src/praisonai-agents/praisonaiagents/memory/protocols.py` |
| Hook system | `src/praisonai-agents/praisonaiagents/hooks/` |
| Event bus | `src/praisonai-agents/praisonaiagents/bus/bus.py` |
| Temporal backend | `src/praisonai-agents/praisonaiagents/temporal/` |
| TS Agent class | `src/praisonai-ts/src/agent/simple.ts` |

## Anti-Patterns (NEVER)
- ❌ Module-level optional imports (`chromadb`, `litellm`, `temporalio`)
- ❌ Heavy implementations in core SDK
- ❌ Shared mutable global state between agents
- ❌ Blocking I/O in async contexts
- ❌ Type suppression (`as any`, `@ts-ignore`, `@ts-expect-error`)
- ❌ Empty catch blocks: `except: pass`
- ❌ Deleting failing tests to "pass"
- ❌ Deprecated params: `allow_code_execution`, `auto_save`, `allow_delegation`
- ❌ Legacy code: `scheduler.py`, `process/process.py`

## CI/CD
- **Manager:** `uv` preferred for Python
- **Versions:** Python 3.10, 3.11
- **Markers:** `-m real` (live APIs), `-m unit` (fast tests), `--pattern fast`

## Package Hierarchy
```
praisonai (Wrapper) → wraps → praisonaiagents (Core SDK)
praisonai-ts (TypeScript) → Parallel implementation
praisonai-rust (Rust) → Parallel implementation
```

## Docker
```bash
docker/Dockerfile           # API service
docker/Dockerfile.chat      # Chat UI
docker/Dockerfile.serve     # Serve mode
docker/docker-compose.yml   # Full stack
```

## Notes & Gotchas
- Sub-AGENTS.md files exist for language-specific SDK internals
- `praisonaiagents` is the source of truth for agent logic
- Plugin template: `examples/python/plugin_template/`
- Always use `uv` for faster dependency management
- Cursor rules in `src/praisonai-agents/.cursorrules`

## Verification Checklist
Before committing:
- [ ] Run tests: `pytest tests/unit/ -v`
- [ ] Check syntax: `python -m py_compile <file>`
- [ ] No module-level optional imports
- [ ] Follow naming conventions
- [ ] Type hints on public APIs
