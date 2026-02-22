"""
Prometheus metrics for Temporal execution backend.

This module provides optional Prometheus metrics collection for
Temporal workflow and activity executions.

Usage:
    from praisonaiagents.temporal.metrics import TemporalMetrics
    
    metrics = TemporalMetrics(enabled=True)
    metrics.record_workflow_start("my-workflow")
    metrics.record_workflow_complete("my-workflow", duration_seconds=1.5)
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class MetricValue:
    """Container for a single metric value."""
    value: float = 0.0
    count: int = 0
    
    def observe(self, value: float):
        """Observe a new value."""
        self.value += value
        self.count += 1
    
    def increment(self, amount: int = 1):
        """Increment counter."""
        self.count += amount


class TemporalMetrics:
    """
    Prometheus-compatible metrics collector for Temporal backend.
    
    Metrics collected:
    - temporal_workflow_total: Counter of workflow executions by status
    - temporal_workflow_duration_seconds: Histogram of workflow durations
    - temporal_activity_total: Counter of activity executions by status
    - temporal_activity_duration_seconds: Histogram of activity durations
    - temporal_connection_retries_total: Counter of connection retry attempts
    - temporal_health_check_total: Counter of health check status
    
    All metrics are optional and have zero overhead when disabled.
    """
    
    def __init__(self, enabled: bool = False, namespace: str = "praisonai"):
        """
        Initialize metrics collector.
        
        Args:
            enabled: Whether to enable Prometheus metrics collection
            namespace: Metrics namespace prefix (default: "praisonai")
        """
        self.enabled = enabled
        self.namespace = namespace
        
        # Internal storage for metrics (lightweight dict-based)
        self._counters: Dict[str, MetricValue] = {}
        self._histograms: Dict[str, list] = {}
        self._gauges: Dict[str, float] = {}
        
        # Prometheus registry (lazy loaded)
        self._registry = None
        self._prom_metrics: Dict[str, Any] = {}
        
        if self.enabled:
            self._init_prometheus_metrics()
    
    def _init_prometheus_metrics(self):
        """Initialize Prometheus metric objects (lazy)."""
        try:
            from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry
            
            self._registry = CollectorRegistry(auto_describe=True)
            
            # Workflow metrics
            self._prom_metrics['workflow_total'] = Counter(
                f'{self.namespace}_temporal_workflow_total',
                'Total number of Temporal workflow executions',
                ['workflow_id', 'status'],
                registry=self._registry
            )
            
            self._prom_metrics['workflow_duration'] = Histogram(
                f'{self.namespace}_temporal_workflow_duration_seconds',
                'Duration of Temporal workflow executions in seconds',
                ['workflow_id'],
                registry=self._registry
            )
            
            # Activity metrics
            self._prom_metrics['activity_total'] = Counter(
                f'{self.namespace}_temporal_activity_total',
                'Total number of Temporal activity executions',
                ['activity_type', 'status'],
                registry=self._registry
            )
            
            self._prom_metrics['activity_duration'] = Histogram(
                f'{self.namespace}_temporal_activity_duration_seconds',
                'Duration of Temporal activity executions in seconds',
                ['activity_type'],
                registry=self._registry
            )
            
            # Connection metrics
            self._prom_metrics['connection_retries'] = Counter(
                f'{self.namespace}_temporal_connection_retries_total',
                'Total number of Temporal connection retry attempts',
                registry=self._registry
            )
            
            self._prom_metrics['health_check'] = Counter(
                f'{self.namespace}_temporal_health_check_total',
                'Total number of Temporal health checks',
                ['status'],
                registry=self._registry
            )
            
            # Health gauge
            self._prom_metrics['healthy'] = Gauge(
                f'{self.namespace}_temporal_healthy',
                'Whether the Temporal connection is healthy (1=healthy, 0=unhealthy)',
                registry=self._registry
            )
            
            logger.debug("Prometheus metrics initialized for Temporal backend")
            
        except ImportError:
            logger.warning(
                "Prometheus metrics requested but 'prometheus_client' not installed. "
                "Install with: pip install prometheus_client"
            )
            self.enabled = False
    
    def record_workflow_start(self, workflow_id: str) -> float:
        """
        Record the start of a workflow execution.
        
        Returns:
            Start timestamp for duration calculation
        """
        if not self.enabled:
            return 0.0
        
        return time.time()
    
    def record_workflow_complete(
        self, 
        workflow_id: str, 
        status: str = "completed",
        start_time: Optional[float] = None
    ):
        """
        Record the completion of a workflow execution.
        
        Args:
            workflow_id: Workflow identifier
            status: Execution status (completed, failed, cancelled)
            start_time: Start timestamp from record_workflow_start()
        """
        if not self.enabled:
            return
        
        # Calculate duration
        duration = 0.0
        if start_time and start_time > 0:
            duration = time.time() - start_time
        
        # Update Prometheus metrics
        if self._registry and 'workflow_total' in self._prom_metrics:
            try:
                self._prom_metrics['workflow_total'].labels(
                    workflow_id=workflow_id, 
                    status=status
                ).inc()
                
                if duration > 0:
                    self._prom_metrics['workflow_duration'].labels(
                        workflow_id=workflow_id
                    ).observe(duration)
            except Exception as e:
                logger.debug(f"Failed to record workflow metrics: {e}")
        
        # Update internal counters
        key = f"workflow.{workflow_id}.{status}"
        if key not in self._counters:
            self._counters[key] = MetricValue()
        self._counters[key].increment()
        
        if duration > 0:
            hist_key = f"workflow.{workflow_id}.duration"
            if hist_key not in self._histograms:
                self._histograms[hist_key] = []
            self._histograms[hist_key].append(duration)
    
    def record_activity_start(self, activity_type: str) -> float:
        """
        Record the start of an activity execution.
        
        Returns:
            Start timestamp for duration calculation
        """
        if not self.enabled:
            return 0.0
        
        return time.time()
    
    def record_activity_complete(
        self,
        activity_type: str,
        status: str = "completed",
        start_time: Optional[float] = None
    ):
        """
        Record the completion of an activity execution.
        
        Args:
            activity_type: Type of activity (e.g., "run_agent_task")
            status: Execution status (completed, failed)
            start_time: Start timestamp from record_activity_start()
        """
        if not self.enabled:
            return
        
        # Calculate duration
        duration = 0.0
        if start_time and start_time > 0:
            duration = time.time() - start_time
        
        # Update Prometheus metrics
        if self._registry and 'activity_total' in self._prom_metrics:
            try:
                self._prom_metrics['activity_total'].labels(
                    activity_type=activity_type,
                    status=status
                ).inc()
                
                if duration > 0:
                    self._prom_metrics['activity_duration'].labels(
                        activity_type=activity_type
                    ).observe(duration)
            except Exception as e:
                logger.debug(f"Failed to record activity metrics: {e}")
        
        # Update internal counters
        key = f"activity.{activity_type}.{status}"
        if key not in self._counters:
            self._counters[key] = MetricValue()
        self._counters[key].increment()
        
        if duration > 0:
            hist_key = f"activity.{activity_type}.duration"
            if hist_key not in self._histograms:
                self._histograms[hist_key] = []
            self._histograms[hist_key].append(duration)
    
    def record_connection_retry(self):
        """Record a connection retry attempt."""
        if not self.enabled:
            return
        
        if self._registry and 'connection_retries' in self._prom_metrics:
            try:
                self._prom_metrics['connection_retries'].inc()
            except Exception as e:
                logger.debug(f"Failed to record connection retry: {e}")
        
        key = "connection.retries"
        if key not in self._counters:
            self._counters[key] = MetricValue()
        self._counters[key].increment()
    
    def record_health_check(self, healthy: bool):
        """
        Record a health check result.
        
        Args:
            healthy: Whether the health check passed
        """
        if not self.enabled:
            return
        
        status = "healthy" if healthy else "unhealthy"
        
        if self._registry and 'health_check' in self._prom_metrics:
            try:
                self._prom_metrics['health_check'].labels(status=status).inc()
                self._prom_metrics['healthy'].set(1 if healthy else 0)
            except Exception as e:
                logger.debug(f"Failed to record health check: {e}")
        
        key = f"health_check.{status}"
        if key not in self._counters:
            self._counters[key] = MetricValue()
        self._counters[key].increment()
        
        self._gauges['healthy'] = 1.0 if healthy else 0.0
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get all collected metrics as a dictionary.
        
        Returns:
            Dictionary containing counters, histograms, and gauges
        """
        return {
            "counters": {
                k: {"count": v.count, "value": v.value} 
                for k, v in self._counters.items()
            },
            "histograms": dict(self._histograms),
            "gauges": dict(self._gauges),
            "enabled": self.enabled,
        }
    
    def export_prometheus(self) -> str:
        """
        Export metrics in Prometheus text format.
        
        Returns:
            Prometheus-formatted metrics string
        """
        if not self.enabled or not self._registry:
            return "# Metrics disabled or prometheus_client not installed\n"
        
        try:
            from prometheus_client import generate_latest
            return generate_latest(self._registry).decode('utf-8')
        except ImportError:
            return "# prometheus_client not installed\n"
        except Exception as e:
            logger.error(f"Failed to export Prometheus metrics: {e}")
            return f"# Error: {e}\n"
    
    def reset(self):
        """Reset all collected metrics."""
        self._counters.clear()
        self._histograms.clear()
        self._gauges.clear()
        logger.debug("Temporal metrics reset")


# Global metrics instance (lazy initialized)
_global_metrics: Optional[TemporalMetrics] = None


def get_metrics(enabled: bool = False) -> TemporalMetrics:
    """
    Get the global Temporal metrics instance.
    
    Args:
        enabled: Whether to enable metrics (only effective on first call)
    
    Returns:
        Global TemporalMetrics instance
    """
    global _global_metrics
    
    if _global_metrics is None:
        _global_metrics = TemporalMetrics(enabled=enabled)
    
    return _global_metrics


def reset_metrics():
    """Reset the global metrics instance."""
    global _global_metrics
    _global_metrics = None
