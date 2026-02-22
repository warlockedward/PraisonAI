from typing import Any
from .protocols import ExecutionBackendProtocol
from .local_backend import LocalExecutionBackend

def get_backend(backend_type: Any = None) -> ExecutionBackendProtocol:
    if backend_type is None or backend_type == "local":
        return LocalExecutionBackend()
    
    is_temporal = backend_type == "temporal" or type(backend_type).__name__ == "TemporalConfig"
    if is_temporal:
        try:
            from praisonaiagents.temporal import TemporalExecutionBackend # type: ignore
            config = backend_type if type(backend_type).__name__ == "TemporalConfig" else None
            return TemporalExecutionBackend(config=config)
        except ImportError as e:
            raise ImportError("The 'temporal' backend requires the 'temporalio' package. Install with: pip install 'praisonaiagents[temporal]'") from e
            
    raise ValueError(f"Unknown execution backend: {backend_type}")
