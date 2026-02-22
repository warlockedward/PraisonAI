from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dataclass
class InterceptorEvent:
    event_type: str
    workflow_id: Optional[str] = None
    activity_id: Optional[str] = None
    agent_name: Optional[str] = None
    task_name: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    payload: Dict[str, Any] = field(default_factory=dict)

class TemporalObserver:
    def on_event(self, event: InterceptorEvent) -> None:
        pass

class EventBusBridge(TemporalObserver):
    def __init__(self, event_bus: Any = None):
        self._event_bus = event_bus
    
    def on_event(self, event: InterceptorEvent) -> None:
        if self._event_bus is None:
            return
        
        try:
            from praisonaiagents.bus import EventBus, get_default_bus
            bus = self._event_bus or get_default_bus()
            bus.emit(
                event.event_type,
                {
                    "workflow_id": event.workflow_id,
                    "activity_id": event.activity_id,
                    "agent_name": event.agent_name,
                    "task_name": event.task_name,
                    "timestamp": event.timestamp,
                    "payload": event.payload
                }
            )
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"Failed to bridge event to EventBus: {e}")

class LoggingObserver(TemporalObserver):
    def __init__(self, level: int = logging.INFO):
        self._level = level
    
    def on_event(self, event: InterceptorEvent) -> None:
        logger.log(
            self._level,
            f"[Temporal] {event.event_type}: workflow={event.workflow_id} "
            f"activity={event.activity_id} agent={event.agent_name}"
        )

class CompositeObserver(TemporalObserver):
    def __init__(self, observers: List[TemporalObserver]):
        self._observers = observers
    
    def on_event(self, event: InterceptorEvent) -> None:
        for observer in self._observers:
            try:
                observer.on_event(event)
            except Exception as e:
                logger.warning(f"Observer failed: {e}")

def create_default_observer(event_bus: Any = None) -> TemporalObserver:
    return CompositeObserver([
        LoggingObserver(),
        EventBusBridge(event_bus)
    ])
