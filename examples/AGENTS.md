# PraisonAI Examples Knowledge Base

**Purpose:** Demonstration code for PraisonAI features. Not production code.
**Root:** `examples/`

## Directory Map
- `python/`: Primary SDK examples (20+ subdirs)
  - `agents/`: Multi-agent patterns
  - `mcp/`: Model Context Protocol (56 files)
  - `models/`: Provider-specific (Grok, Kimi, etc.)
  - `workflows/`: Workflow patterns
  - `usecases/`: Real-world scenarios
  - `plugin_template/`: Canonical plugin pattern
- `yaml/`: YAML-configured agents (41 files)
- `js/`: TypeScript/JS SDK examples
- `cookbooks/`: End-to-end recipes (YAML/Python)
- `knowledge/` / `rag/`: RAG and Knowledge Base
- `memory/`: Memory system implementations
- `tools/`: Tool creation examples
- `guardrails/`: Safety and validation
- `eval/`: Evaluation framework

## Navigation Guide
| I want to... | Go to |
| :--- | :--- |
| Basic agent | `examples/python/general/` |
| Multi-agent patterns | `examples/python/agents/` or `examples/multi_agent/` |
| MCP integration | `examples/python/mcp/` |
| Tool creation | `examples/tools/` |
| Memory examples | `examples/memory/` |
| RAG/Knowledge | `examples/knowledge/` or `examples/rag/` |
| YAML config | `examples/yaml/` |
| Guardrails/Safety | `examples/guardrails/` |
| Provider-specific | `examples/python/models/` |
| Scheduling | `examples/scheduler/` |
| Plugin creation | `examples/python/plugin_template/` |
| Evaluation | `examples/eval/` |

## Plugin Template
Use `examples/python/plugin_template/` for external pip tools.
Register in `pyproject.toml`:
```toml
[project.entry-points."praisonaiagents.tools"]
my_tool = "my_package.tools:MyTool"
```

## Gotchas
- `examples/python/mcp/` is extensive (56 files); check before adding.
- `examples/consolidated_params/` shows `Config` object patterns.
- `run_all_examples.py` at root is for smoke testing.
- Examples are NOT tests; do not use `pytest` here.
- Minimal setup: examples should run with minimal configuration.
