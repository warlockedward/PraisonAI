from .config import TemporalConfig

def __getattr__(name: str):
    if name in ("TemporalExecutionBackend", "TemporalWorker"):
        try:
            import temporalio # type: ignore # noqa: F401
        except ImportError as e:
            raise ImportError(
                f"'{name}' requires temporalio. Install with: pip install 'praisonaiagents[temporal]'"
            ) from e
        if name == "TemporalExecutionBackend":
            from .backend import TemporalExecutionBackend # type: ignore
            return TemporalExecutionBackend
    raise AttributeError(f"module 'praisonaiagents.temporal' has no attribute {name!r}")

__all__ = ["TemporalConfig"]
