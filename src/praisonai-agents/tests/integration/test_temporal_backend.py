import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from praisonaiagents.temporal.config import TemporalConfig
from praisonaiagents.temporal.backend import TemporalExecutionBackend

@pytest.mark.asyncio
async def test_temporal_backend_initialization():
    config = TemporalConfig(address="test:7233", start_worker=False)
    backend = TemporalExecutionBackend(config)
    assert backend.config.address == "test:7233"
    assert backend._client is None
    assert backend._worker_task is None

@pytest.mark.asyncio
async def test_get_client():
    mock_client = MagicMock()
    
    with patch('temporalio.client.Client.connect', new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_client
        
        config = TemporalConfig(address="test:7233", start_worker=False)
        backend = TemporalExecutionBackend(config)
        
        client = await backend._get_client()
        assert client == mock_client
        mock_connect.assert_called_once()
