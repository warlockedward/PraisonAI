# PraisonAI CLI Subsystem

**Package:** `praisonai/praisonai/cli/`
**Purpose:** CLI entry point and command/feature subsystem for the PraisonAI wrapper.

## Structure
- `main.py`: Primary CLI entry point. Includes security warning for sensitive content.
- `app.py`: CLI app definition (Typer-based).
- `commands/`: 61 command modules (thin CLI handlers).
- `features/`: 97 feature modules (business logic implementations).

## CLI Entry Points
| Command | Script | pyproject.toml |
|---------|--------|----------------|
| `praisonai` | `praisonai.__main__:main` | main entry |
| `praisonai-call` | `praisonai.api.call:main` | call API |
| `setup-conda-env` | `praisonai.setup.setup_conda_env:main` | env setup |

## Adding Commands (Pattern)
```python
import typer
app = typer.Typer()

@app.command()
def my_command(prompt: str):
    """Command description."""
    ...
```

## Critical Conventions (recipe_creator.py / recipe_optimizer.py)
- ALWAYS include `OPENAI_API_KEY` in recipes.
- If tools assigned: ALWAYS add `tool_choice: required`.
- MANDATORY YAML fields: `process`, `manager_llm`, `agent roles`.
- Optimization: ALWAYS preserve `process: hierarchical` and `manager_llm`.

## Framework & Tools
- **Typer:** `typer>=0.9.0` (CLI framework).
- **Terminal UI:** `textual>=0.47.0` (TUI commands).

## Testing
- **Location:** `src/praisonai/tests/unit/cli/`
- **Command:** `python -m pytest tests/unit/cli/ -v`

## Gotchas
- `commands/` vs `features/`: Commands are thin handlers; Features are logic.
- Check existing: 97 features and 61 commands already exist.
- Security: `main.py` sensitive content detection must remain enabled.
