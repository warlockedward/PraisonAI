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

@pytest.mark.asyncio
async def test_get_status():
    mock_client = MagicMock()
    mock_handle = MagicMock()
    mock_description = MagicMock()
    mock_description.status.name = "RUNNING"
    mock_description.start_time = "2024-01-01T00:00:00"
    mock_description.close_time = None
    mock_description.history_length = 10
    
    mock_handle.describe = AsyncMock(return_value=mock_description)
    mock_client.get_workflow_handle = MagicMock(return_value=mock_handle)
    
    with patch('temporalio.client.Client.connect', new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_client
        
        config = TemporalConfig(address="test:7233", start_worker=False)
        backend = TemporalExecutionBackend(config)
        
        status = await backend.get_status("test-workflow-id")
        assert status["status"] == "RUNNING"
        assert status["execution_id"] == "test-workflow-id"
        mock_client.get_workflow_handle.assert_called_once_with("test-workflow-id")

@pytest.mark.asyncio
async def test_send_signal():
    mock_client = MagicMock()
    mock_handle = MagicMock()
    mock_handle.signal = AsyncMock()
    mock_client.get_workflow_handle = MagicMock(return_value=mock_handle)
    
    with patch('temporalio.client.Client.connect', new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_client
        
        config = TemporalConfig(address="test:7233", start_worker=False)
        backend = TemporalExecutionBackend(config)
        
        await backend.send_signal("test-workflow-id", "cancel_task", {"task_id": "123"})
        mock_handle.signal.assert_called_once_with("cancel_task", {"task_id": "123"})

@pytest.mark.asyncio
async def test_cancel():
    mock_client = MagicMock()
    mock_handle = MagicMock()
    mock_handle.cancel = AsyncMock()
    mock_client.get_workflow_handle = MagicMock(return_value=mock_handle)
    
    with patch('temporalio.client.Client.connect', new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_client
        
        config = TemporalConfig(address="test:7233", start_worker=False)
        backend = TemporalExecutionBackend(config)
        
        await backend.cancel("test-workflow-id")
        mock_handle.cancel.assert_called_once()

@pytest.mark.asyncio
async def test_is_healthy():
    mock_client = MagicMock()
    mock_client.service_client = MagicMock()
    mock_client.service_client.health_check = AsyncMock()
    
    with patch('temporalio.client.Client.connect', new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_client
        
        config = TemporalConfig(address="test:7233", start_worker=False)
        backend = TemporalExecutionBackend(config)
        
        # Initialize client
        await backend._get_client()
        
        # Check health
        is_healthy = await backend.is_healthy()
        assert is_healthy is True
        mock_client.service_client.health_check.assert_called()

@pytest.mark.asyncio
async def test_is_healthy_no_client():
    config = TemporalConfig(address="test:7233", start_worker=False)
    backend = TemporalExecutionBackend(config)
    
    is_healthy = await backend.is_healthy()
    assert is_healthy is False

@pytest.mark.asyncio
async def test_connection_retry():
    mock_client = MagicMock()
    
    with patch('temporalio.client.Client.connect', new_callable=AsyncMock) as mock_connect:
        # First attempt fails, second succeeds
        mock_connect.side_effect = [ConnectionError("Connection refused"), mock_client]
        
        config = TemporalConfig(
            address="test:7233", 
            start_worker=False,
            connect_retries=3
        )
        backend = TemporalExecutionBackend(config)
        
        client = await backend._get_client()
        assert client == mock_client
        assert mock_connect.call_count == 2

@pytest.mark.asyncio
async def test_connection_retry_exhausted():
    with patch('temporalio.client.Client.connect', new_callable=AsyncMock) as mock_connect:
        # All attempts fail
        mock_connect.side_effect = ConnectionError("Connection refused")
        
        config = TemporalConfig(
            address="test:7233", 
            start_worker=False,
            connect_retries=2
        )
        backend = TemporalExecutionBackend(config)
        
        with pytest.raises(ConnectionError) as exc_info:
            await backend._get_client()
        
        assert "Failed to connect" in str(exc_info.value)
        assert mock_connect.call_count == 2

@pytest.mark.asyncio
async def test_close_cancels_health_check():
    mock_client = MagicMock()
    mock_client.service_client = MagicMock()
    mock_client.service_client.health_check = AsyncMock()
    
    with patch('temporalio.client.Client.connect', new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = mock_client
        
        config = TemporalConfig(address="test:7233", start_worker=False)
        backend = TemporalExecutionBackend(config)
        
        # Initialize client (starts health check task)
        await backend._get_client()
        
        # Verify health check task is running
        assert backend._health_check_task is not None
        
        # Close should cancel health check task
        await backend.close()
        assert backend._health_check_task is None
        assert backend._client is None
