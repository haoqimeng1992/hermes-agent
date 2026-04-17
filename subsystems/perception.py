# Perception — 感知层

"""
从环境获取信息

感知维度：
- 用户输入感知（消息、语气、意图）
- 系统状态感知（负载、错误率、资源使用）
- 外部变化感知（时间、上下文长度、工具可用性）
- 上下文感知（对话历史、当前状态）

设计原理：
- 感知是智能的入口
- 好的感知系统能在问题发生前就察觉到信号
"""

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

HERMES_HOME = Path.home() / ".hermes"
PERCEPTION_DIR = HERMES_HOME / "knowledge" / "perception"


class PerceptionSource(Enum):
    USER_MESSAGE = "user_message"       # 用户输入
    SYSTEM_METRICS = "system_metrics"   # 系统指标
    CONTEXT_STATE = "context_state"     # 上下文状态
    EXTERNAL_EVENT = "external_event"   # 外部事件
    TIME_TRIGGER = "time_trigger"       # 时间触发
    TOOL_RESULT = "tool_result"        # 工具结果


@dataclass
class PerceptionSignal:
    """感知信号"""
    id: str
    source: PerceptionSource
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    content: Any = None                  # 信号内容
    metadata: dict = field(default_factory=dict)
    urgency: float = 0.0                # 紧急程度 0-1
    confidence: float = 1.0             # 置信度 0-1
    processed: bool = False              # 是否已处理
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source": self.source.value,
            "timestamp": self.timestamp,
            "content": str(self.content),
            "metadata": self.metadata,
            "urgency": self.urgency,
            "confidence": self.confidence,
            "processed": self.processed,
        }


@dataclass
class PerceptionProfile:
    """感知画像 — 当前感知状态摘要"""
    active_signals: int = 0
    high_urgency_signals: int = 0
    avg_confidence: float = 1.0
    dominant_source: Optional[PerceptionSource] = None
    recent_themes: list[str] = field(default_factory=list)


class PerceptionLayer:
    """
    感知层 — 从环境获取信息
    
    核心职责：
    1. 接收并分类各类感知信号
    2. 评估信号紧急程度
    3. 检测异常模式和预警信号
    4. 为决策层提供感知摘要
    
    感知 → 分类 → 紧急评估 → 异常检测 → 摘要
    """
    
    def __init__(self):
        PERCEPTION_DIR.mkdir(parents=True, exist_ok=True)
        self.signals: list[PerceptionSignal] = []
        self._signal_counter = 0
        
        # 异常检测模式
        self._anomaly_patterns = [
            ("repeated_timeout", self._detect_timeout_pattern),
            ("error_rate_spike", self._detect_error_spike),
            ("context_overflow", self._detect_context_overflow),
            ("latency_degradation", self._detect_latency_degradation),
        ]
    
    # === 信号接收 ===
    
    def perceive(
        self,
        source: PerceptionSource,
        content: Any,
        metadata: dict = None,
        urgency: float = 0.0,
    ) -> PerceptionSignal:
        """接收一个感知信号"""
        self._signal_counter += 1
        signal = PerceptionSignal(
            id=f"sig_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self._signal_counter}",
            source=source,
            content=content,
            metadata=metadata or {},
            urgency=urgency,
        )
        
        # 自动评估紧急程度
        if urgency == 0.0:
            signal.urgency = self._assess_urgency(signal)
        
        # 自动异常检测
        for pattern_name, detector_fn in self._anomaly_patterns:
            if detector_fn(signal):
                signal.metadata["anomaly_detected"] = pattern_name
                signal.urgency = max(signal.urgency, 0.7)
        
        self.signals.append(signal)
        
        # 保持最近1000条信号
        if len(self.signals) > 1000:
            self.signals = self.signals[-1000:]
        
        return signal
    
    def perceive_user_message(self, message: str, **metadata) -> PerceptionSignal:
        """感知用户消息"""
        urgency = 0.0
        
        # 紧急关键词
        urgent_keywords = ["紧急", "快", "马上", "立即", "救命", "help", "urgent", "asap"]
        if any(kw in message.lower() for kw in urgent_keywords):
            urgency = 0.8
        
        # 重复内容检测
        if self._is_repeated_message(message):
            metadata["repeated"] = True
            metadata["repeat_count"] = metadata.get("repeat_count", 0) + 1
        
        return self.perceive(
            source=PerceptionSource.USER_MESSAGE,
            content=message,
            metadata=metadata,
            urgency=urgency,
        )
    
    def perceive_system_metrics(self, metrics: dict, **metadata) -> PerceptionSignal:
        """感知系统指标"""
        urgency = 0.0
        
        # 错误率检测
        if metrics.get("error_rate", 0) > 0.05:
            urgency = max(urgency, 0.7)
        
        # 资源使用检测
        if metrics.get("cpu_percent", 0) > 80:
            urgency = max(urgency, 0.6)
        
        return self.perceive(
            source=PerceptionSource.SYSTEM_METRICS,
            content=metrics,
            metadata=metadata,
            urgency=urgency,
        )
    
    def perceive_context_state(
        self,
        token_count: int,
        message_count: int,
        compression_ratio: float = 0.0,
    ) -> PerceptionSignal:
        """感知上下文状态"""
        urgency = 0.0
        
        # 上下文即将溢出预警
        if token_count > 150000:
            urgency = max(urgency, 0.8)
        elif token_count > 100000:
            urgency = max(urgency, 0.5)
        
        return self.perceive(
            source=PerceptionSource.CONTEXT_STATE,
            content={
                "token_count": token_count,
                "message_count": message_count,
                "compression_ratio": compression_ratio,
            },
            metadata={},
            urgency=urgency,
        )
    
    def perceive_tool_result(
        self,
        tool_name: str,
        result: Any,
        duration_ms: float,
        error: bool = False,
    ) -> PerceptionSignal:
        """感知工具执行结果"""
        urgency = 0.0
        if error:
            urgency = 0.6
        
        # 慢工具检测
        if duration_ms > 30000:  # 30秒
            urgency = max(urgency, 0.4)
        
        return self.perceive(
            source=PerceptionSource.TOOL_RESULT,
            content={"tool_name": tool_name, "duration_ms": duration_ms, "error": error},
            metadata={"duration_ms": duration_ms},
            urgency=urgency,
        )
    
    # === 异常检测 ===
    
    def _detect_timeout_pattern(self, signal: PerceptionSignal) -> bool:
        """检测超时模式"""
        if signal.source == PerceptionSource.TOOL_RESULT:
            content = signal.content if isinstance(signal.content, dict) else {}
            if content.get("duration_ms", 0) > 60000:  # 60秒超时
                return True
        return False
    
    def _detect_error_spike(self, signal: PerceptionSignal) -> bool:
        """检测错误率飙升"""
        if signal.source == PerceptionSource.SYSTEM_METRICS:
            metrics = signal.content if isinstance(signal.content, dict) else {}
            if metrics.get("error_rate", 0) > metrics.get("baseline_error_rate", 0.01) * 3:
                return True
        return False
    
    def _detect_context_overflow(self, signal: PerceptionSignal) -> bool:
        """检测上下文溢出"""
        if signal.source == PerceptionSource.CONTEXT_STATE:
            content = signal.content if isinstance(signal.content, dict) else {}
            if content.get("token_count", 0) > 180000:
                return True
        return False
    
    def _detect_latency_degradation(self, signal: PerceptionSignal) -> bool:
        """检测延迟退化"""
        if signal.source == PerceptionSource.TOOL_RESULT:
            content = signal.content if isinstance(signal.content, dict) else {}
            duration = content.get("duration_ms", 0)
            if duration > 10000 and signal.metadata.get("baseline_duration_ms", 1000) > 0:
                ratio = duration / signal.metadata.get("baseline_duration_ms", 1000)
                if ratio > 5:  # 延迟增加5倍以上
                    return True
        return False
    
    # === 紧急评估 ===
    
    def _assess_urgency(self, signal: PerceptionSignal) -> float:
        """评估信号紧急程度"""
        base_urgency = 0.0
        
        if signal.source == PerceptionSource.USER_MESSAGE:
            base_urgency = 0.3
        
        elif signal.source == PerceptionSource.SYSTEM_METRICS:
            base_urgency = 0.4
        
        elif signal.source == PerceptionSource.CONTEXT_STATE:
            content = signal.content if isinstance(signal.content, dict) else {}
            token_count = content.get("token_count", 0)
            if token_count > 150000:
                base_urgency = 0.9
            elif token_count > 100000:
                base_urgency = 0.6
        
        elif signal.source == PerceptionSource.TOOL_RESULT:
            base_urgency = 0.2
        
        return base_urgency
    
    def _is_repeated_message(self, message: str) -> bool:
        """检测重复消息"""
        recent_messages = [
            s.content for s in self.signals[-10:]
            if s.source == PerceptionSource.USER_MESSAGE and isinstance(s.content, str)
        ]
        return message in recent_messages[-3:-1] if len(recent_messages) > 1 else False
    
    # === 信号处理 ===
    
    def get_unprocessed_signals(self) -> list[PerceptionSignal]:
        """获取未处理的信号"""
        return [s for s in self.signals if not s.processed]
    
    def get_high_urgency_signals(self, threshold: float = 0.7) -> list[PerceptionSignal]:
        """获取高紧急信号"""
        return [s for s in self.signals if s.urgency >= threshold]
    
    def mark_processed(self, signal_id: str):
        """标记信号已处理"""
        for signal in self.signals:
            if signal.id == signal_id:
                signal.processed = True
                break
    
    def clear_processed(self):
        """清除已处理的信号"""
        self.signals = [s for s in self.signals if not s.processed]
    
    # === 感知摘要 ===
    
    def get_profile(self) -> PerceptionProfile:
        """获取当前感知画像"""
        recent = self.signals[-100:]  # 最近100条
        
        high_urgency = [s for s in recent if s.urgency >= 0.7]
        
        # 主导源
        source_counts = {}
        for s in recent:
            source_counts[s.source] = source_counts.get(s.source, 0) + 1
        dominant = max(source_counts, key=source_counts.get) if source_counts else None
        
        # 最近主题
        themes = []
        for s in recent:
            if s.source == PerceptionSource.USER_MESSAGE and isinstance(s.content, str):
                themes.append(s.content[:50])
        
        return PerceptionProfile(
            active_signals=len(recent),
            high_urgency_signals=len(high_urgency),
            avg_confidence=sum(s.confidence for s in recent) / len(recent) if recent else 1.0,
            dominant_source=dominant,
            recent_themes=themes[-5:],
        )
    
    def get_summary(self) -> dict:
        """获取感知层摘要"""
        profile = self.get_profile()
        anomaly_signals = [s for s in self.signals if s.metadata.get("anomaly_detected")]
        
        return {
            "total_signals": len(self.signals),
            "active_signals": profile.active_signals,
            "high_urgency_signals": profile.high_urgency_signals,
            "avg_confidence": round(profile.avg_confidence, 2),
            "dominant_source": profile.dominant_source.value if profile.dominant_source else None,
            "anomaly_detections": len(anomaly_signals),
            "recent_anomalies": [
                {"id": s.id, "type": s.metadata.get("anomaly_detected")}
                for s in anomaly_signals[-5:]
            ],
        }


# 全局单例
_perception: Optional[PerceptionLayer] = None

def get_perception() -> PerceptionLayer:
    global _perception
    if _perception is None:
        _perception = PerceptionLayer()
    return _perception
