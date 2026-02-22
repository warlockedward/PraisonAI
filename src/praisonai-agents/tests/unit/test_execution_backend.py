import pytest
from praisonaiagents.execution.registry import get_backend
from praisonaiagents.execution.local_backend import LocalExecutionBackend
from praisonaiagents.execution.protocols import ExecutionBackendProtocol

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
    import importlib
    if importlib.util.find_spec("temporalio") is not None:
        pytest.skip("temporalio is installed, cannot test ImportError")
    with pytest.raises(ImportError, match="temporalio"):
        get_backend("temporal")

def test_get_backend_unknown_raises():
    with pytest.raises(ValueError, match="Unknown execution backend: unknown_backend"):
        get_backend("unknown_backend")
