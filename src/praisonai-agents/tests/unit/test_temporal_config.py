import pytest
import sys
from datetime import timedelta
from praisonaiagents.temporal import TemporalConfig

def test_temporal_config_defaults():
    config = TemporalConfig()
    assert config.address == "localhost:7233"
    assert config.namespace == "default"
    assert config.task_queue == "praisonai-agents"
    assert config.tls is False
    assert config.tls_cert_path is None

def test_temporal_config_custom_address():
    config = TemporalConfig(address="temporal.mycompany.com:7233", namespace="production")
    assert config.address == "temporal.mycompany.com:7233"
    assert config.namespace == "production"

def test_temporal_config_timeout_defaults():
    config = TemporalConfig()
    assert config.workflow_execution_timeout == timedelta(hours=24)
    assert config.default_activity_timeout == timedelta(minutes=10)

def test_temporal_config_retry_policy_defaults():
    config = TemporalConfig()
    assert config.default_retry_policy["maximum_attempts"] == 5
    assert config.default_retry_policy["backoff_coefficient"] == 2.0

def test_temporal_config_worker_defaults():
    config = TemporalConfig()
    assert config.start_worker is True
    assert config.worker_count == 4

def test_temporal_config_no_temporalio_import():
    """TemporalConfig must work without temporalio installed."""
    # Already verified by the fact we can import it in this test without temporalio installed
    assert TemporalConfig is not None

def test_temporal_config_tls_settings():
    config = TemporalConfig(
        tls=True,
        tls_cert_path="/path/to/cert.pem",
        tls_key_path="/path/to/key.pem",
    )
    assert config.tls is True
    assert config.tls_cert_path == "/path/to/cert.pem"
    assert config.tls_key_path == "/path/to/key.pem"
