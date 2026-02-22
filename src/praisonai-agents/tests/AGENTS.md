# PraisonAI Agents Test Suite

**Package:** `src/praisonai-agents/tests/`
**Framework:** pytest + pytest-asyncio + pytest-cov
**Scale:** 226 files (largest single directory in repo)

## Test Structure
- `unit/`: Fast, isolated tests (58 files). No external API calls.
- `integration/`: Cross-module tests (20 files). May use mocks.
- `conftest.py`: Shared fixtures and pytest plugins.
- `pytest.ini`: Pytest configuration.
- `fixtures/`: Test data.

## Run Commands
```bash
pytest tests/                                # All tests
pytest tests/unit/                           # Unit only (fast)
pytest tests/integration/                    # Integration
pytest --cov=praisonaiagents tests/          # With coverage
pytest tests/ -m real                        # Real API tests
pytest tests/unit/test_injected_state.py -v  # Specific file
```

## Test Conventions
- TDD mandatory: write failing test FIRST.
- `pytest-asyncio` for async tests (`@pytest.mark.asyncio`).
- `@pytest.mark.real` for tests needing live API keys.
- `human_input_mode="NEVER"` for automated agent tests.
- Deterministic: no dependency on timing or external state.
- Mock external APIs in unit tests.

## Example Unit Test Pattern
```python
import pytest
from praisonaiagents import Agent, Task

def test_agent_creation():
    agent = Agent(name="test", instructions="Be helpful")
    assert agent.name == "test"

@pytest.mark.asyncio
async def test_async_agent():
    agent = Agent(name="test", instructions="Be helpful")
    # mock LLM here
    ...
```

## Environment Variables
| Variable | Purpose | CI Fallback |
|----------|---------|------------|
| `OPENAI_API_KEY` | OpenAI API | Test key (limited) |
| `ANTHROPIC_API_KEY` | Anthropic API | Required for `@pytest.mark.real` |
| `PRAISONAI_TELEMETRY` | Disable telemetry | `false` |

## Coverage
- Target: `--cov=praisonaiagents --cov-report=term-missing`
- CI: Uploads to Codecov via `coverage.yml`.
- Branch coverage enabled: `--cov-branch`.

## Gotchas
- 226 files: check if test exists before adding.
- `conftest.py`: use shared fixtures, don't duplicate.
- `unit/`: fully isolated (no network, no filesystem writes).
- `integration/`: clean up temp dirs in fixtures.
- `pytest.ini`: discovery patterns; keep tests in standard dirs.
