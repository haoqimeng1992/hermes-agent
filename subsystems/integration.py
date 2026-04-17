# Integration — 集成层

"""
将各子系统整合为一个有机整体

集成维度：
- 数据流集成（子系统间的数据传递）
- 控制流集成（统一的调用入口）
- 状态同步（跨子系统的状态一致性）
- 事件总线（统一的事件发布/订阅）

设计原理：
- 子系统不应该是一盘散沙
- 好的集成让整体大于部分之和
- 集成层负责协调和同步
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional
import asyncio

HERMES_HOME = Path.home() / ".hermes"
INTEGRATION_DIR = HERMES_HOME / "knowledge" / "integration"


class EventType(Enum):
    # 感知事件
    SIGNAL_RECEIVED = "signal_received"
    ANOMALY_DETECTED = "anomaly_detected"
    
    # 记忆事件
    MEMORY_STORED = "memory_stored"
    MEMORY_RETRIEVED = "memory_retrieved"
    MEMORY_FORGOTTEN = "memory_forgotten"
    
    # 知识事件
    KNOWLEDGE_ACQUIRED = "knowledge_acquired"
    KNOWLEDGE_VERIFIED = "knowledge_verified"
    
    # 反思事件
    REFLECTION_RECORDED = "reflection_recorded"
    INSIGHT_GENERATED = "insight_generated"
    
    # 进化事件
    EVOLUTION_PROPOSED = "evolution_proposed"
    EVOLUTION_ADOPTED = "evolution_adopted"
    EVOLUTION_REJECTED = "evolution_rejected"
    
    # 治理事件
    ACTION_BLOCKED = "action_blocked"
    ACTION_APPROVED = "action_approved"
    
    # 编排事件
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    
    # 系统事件
    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"


@dataclass
class Event:
    """系统事件"""
    id: str
    type: EventType
    source: str                          # 事件来源子系统
    data: Any = None                     # 事件数据
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    correlation_id: str = ""             # 关联ID（用于追踪）
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "source": self.source,
            "data": str(self.data) if self.data else None,
            "timestamp": self.timestamp,
            "correlation_id": self.correlation_id,
            "metadata": self.metadata,
        }


class EventBus:
    """事件总线 — 统一的发布/订阅"""
    
    def __init__(self):
        self._subscribers: dict[EventType, list[Callable]] = {}
        self._event_log: list[Event] = []
    
    def subscribe(self, event_type: EventType, handler: Callable[[Event], None]):
        """订阅事件"""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
    
    def unsubscribe(self, event_type: EventType, handler: Callable[[Event], None]):
        """取消订阅"""
        if event_type in self._subscribers:
            self._subscribers[event_type] = [
                h for h in self._subscribers[event_type] if h != handler
            ]
    
    def publish(self, event: Event):
        """发布事件"""
        self._event_log.append(event)
        
        # 保持最近1000条
        if len(self._event_log) > 1000:
            self._event_log = self._event_log[-1000:]
        
        # 通知订阅者
        if event.type in self._subscribers:
            for handler in self._subscribers[event.type]:
                try:
                    handler(event)
                except Exception:
                    pass  # 不影响其他订阅者
    
    def get_recent_events(self, event_type: EventType = None, limit: int = 50) -> list[Event]:
        """获取最近事件"""
        events = self._event_log
        if event_type:
            events = [e for e in events if e.type == event_type]
        return events[-limit:]


@dataclass
class DataFlow:
    """数据流记录"""
    from_subsystem: str
    to_subsystem: str
    data_type: str
    data_summary: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    latency_ms: float = 0.0


class IntegrationLayer:
    """
    集成层 — 将各子系统整合为有机整体
    
    核心职责：
    1. 事件总线（统一发布/订阅）
    2. 数据流协调
    3. 状态同步
    4. 子系统生命周期管理
    
    事件总线 ←→ 数据流 ←→ 状态同步 ←→ 生命周期管理
    """
    
    def __init__(self):
        INTEGRATION_DIR.mkdir(parents=True, exist_ok=True)
        self.event_bus = EventBus()
        self._data_flows: list[DataFlow] = []
        self._subsystem_status: dict[str, str] = {}
        self._subsystems: dict[str, Any] = {}
    
    # === 子系统注册 ===
    
    def register_subsystem(self, name: str, instance: Any):
        """注册子系统"""
        self._subsystems[name] = instance
        self._subsystem_status[name] = "registered"
        self.event_bus.publish(Event(
            id=f"evt_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            type=EventType.SYSTEM_STARTUP,
            source="integration",
            data={"subsystem": name, "status": "registered"},
        ))
    
    def get_subsystem(self, name: str) -> Optional[Any]:
        """获取子系统实例"""
        return self._subsystems.get(name)
    
    def set_subsystem_status(self, name: str, status: str):
        """设置子系统状态"""
        self._subsystem_status[name] = status
    
    # === 事件总线 ===
    
    def on(self, event_type: EventType, handler: Callable[[Event], None]):
        """订阅事件"""
        self.event_bus.subscribe(event_type, handler)
    
    def off(self, event_type: EventType, handler: Callable[[Event], None]):
        """取消订阅"""
        self.event_bus.unsubscribe(event_type, handler)
    
    def emit(self, event_type: EventType, source: str, data: Any = None, **metadata):
        """发布事件"""
        event = Event(
            id=f"evt_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            type=event_type,
            source=source,
            data=data,
            metadata=metadata,
        )
        self.event_bus.publish(event)
        return event
    
    # === 数据流 ===
    
    def record_data_flow(
        self,
        from_subsystem: str,
        to_subsystem: str,
        data_type: str,
        data: Any,
        latency_ms: float = 0.0,
    ):
        """记录数据流"""
        data_summary = str(data)[:100] if data else ""
        
        flow = DataFlow(
            from_subsystem=from_subsystem,
            to_subsystem=to_subsystem,
            data_type=data_type,
            data_summary=data_summary,
            latency_ms=latency_ms,
        )
        self._data_flows.append(flow)
        
        # 保持最近1000条
        if len(self._data_flows) > 1000:
            self._data_flows = self._data_flows[-1000:]
    
    def get_data_flows(
        self,
        from_subsystem: str = None,
        to_subsystem: str = None,
        limit: int = 50,
    ) -> list[DataFlow]:
        """获取数据流"""
        flows = self._data_flows
        if from_subsystem:
            flows = [f for f in flows if f.from_subsystem == from_subsystem]
        if to_subsystem:
            flows = [f for f in flows if f.to_subsystem == to_subsystem]
        return flows[-limit:]
    
    # === 跨子系统调用 ===
    
    async def call_subsystem(
        self,
        subsystem_name: str,
        method_name: str,
        *args,
        **kwargs,
    ) -> Any:
        """跨子系统调用"""
        subsystem = self._subsystems.get(subsystem_name)
        if not subsystem:
            raise ValueError(f"子系统不存在: {subsystem_name}")
        
        method = getattr(subsystem, method_name, None)
        if not method:
            raise ValueError(f"子系统 {subsystem_name} 没有方法 {method_name}")
        
        # 记录数据流
        start_time = datetime.now()
        
        try:
            if asyncio.iscoroutinefunction(method):
                result = await method(*args, **kwargs)
            else:
                result = method(*args, **kwargs)
            
            # 记录延迟
            latency_ms = (datetime.now() - start_time).total_seconds() * 1000
            self.record_data_flow(
                from_subsystem="integration",
                to_subsystem=subsystem_name,
                data_type=f"method_call:{method_name}",
                data=result,
                latency_ms=latency_ms,
            )
            
            return result
        
        except Exception as e:
            self.record_data_flow(
                from_subsystem="integration",
                to_subsystem=subsystem_name,
                data_type=f"method_call:{method_name}",
                data=f"error: {str(e)}",
                latency_ms=(datetime.now() - start_time).total_seconds() * 1000,
            )
            raise
    
    # === 状态查询 ===
    
    def get_subsystem_status(self) -> dict[str, str]:
        """获取所有子系统状态"""
        return self._subsystem_status.copy()
    
    def get_all_events(self, limit: int = 100) -> list[Event]:
        """获取所有事件"""
        return self.event_bus.get_recent_events(limit=limit)
    
    def get_event_counts(self) -> dict[str, int]:
        """获取各类型事件数量"""
        counts = {}
        for event in self._data_flows:  # 使用内部事件日志
            pass  # 需要从 event_bus 获取
        return counts
    
    # === 摘要 ===
    
    def get_summary(self) -> dict:
        """获取集成层摘要"""
        return {
            "registered_subsystems": len(self._subsystems),
            "subsystem_status": self._subsystem_status,
            "total_events": len(self.event_bus._event_log),
            "total_data_flows": len(self._data_flows),
            "event_types": list(set(e.type.value for e in self.event_bus._event_log)),
        }


# 全局单例
_integration: Optional[IntegrationLayer] = None

def get_integration() -> IntegrationLayer:
    global _integration
    if _integration is None:
        _integration = IntegrationLayer()
    return _integration
