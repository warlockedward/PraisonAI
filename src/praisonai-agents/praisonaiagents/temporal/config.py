from dataclasses import dataclass, field
from datetime import timedelta
from typing import Optional, Dict, Any, List

@dataclass
class TemporalConfig:
    address: str = "localhost:7233"
    namespace: str = "default"
    task_queue: str = "praisonai-agents"

    tls: bool = False
    tls_cert_path: Optional[str] = None
    tls_key_path: Optional[str] = None

    workflow_execution_timeout: timedelta = field(default_factory=lambda: timedelta(hours=24))
    default_activity_timeout: timedelta = field(default_factory=lambda: timedelta(minutes=10))

    default_retry_policy: Dict[str, Any] = field(default_factory=lambda: {
        "maximum_attempts": 5,
        "initial_interval": 1,
        "backoff_coefficient": 2.0,
        "maximum_interval": 300,
    })

    start_worker: bool = True
    worker_count: int = 4

    data_converter: Optional[Any] = None
    interceptors: Optional[List[Any]] = None
    
    connect_timeout: timedelta = field(default_factory=lambda: timedelta(seconds=30))
    connect_retries: int = 3
    connect_retry_delay: timedelta = field(default_factory=lambda: timedelta(seconds=1))
    health_check_interval: timedelta = field(default_factory=lambda: timedelta(seconds=30))
    
    # Metrics configuration
    enable_prometheus_metrics: bool = False
    
    @property
    def activity_timeout(self) -> timedelta:
        """Alias for default_activity_timeout for use in activity execution."""
        return self.default_activity_timeout
